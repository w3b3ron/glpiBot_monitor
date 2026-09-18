import asyncio
import logging
from datetime import datetime, time, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application

from app import config
from app import database, queries, analytics_service


def get_next_run(now: datetime) -> datetime:
    """Calcula o próximo horário de disparo agendado com base em config.SCHEDULE_TIMES."""
    candidates = []
    today = now.date()

    for time_str in config.SCHEDULE_TIMES:
        try:
            parts = time_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            t = datetime.combine(today, time(h, m))
            if t <= now:
                t += timedelta(days=1)
            candidates.append(t)
        except Exception as e:
            logging.error(f"Formato inválido de horário em SCHEDULE_TIMES ({time_str}): {e}")

    if not candidates:
        # Padrão 07:30
        t = datetime.combine(today, time(7, 30))
        if t <= now:
            t += timedelta(days=1)
        return t

    return min(candidates)


async def trigger_manager_report_prompt(telegram_app: Application):
    """
    Envia o prompt interativo para os gestores cadastrados e grupos autorizados
    oferecendo o envio do relatório por e-mail mediante confirmação.
    """
    logging.info("📢 Disparando alerta agendado de relatório GLPI para gestores no Telegram...")

    managers = config.get_managers_map()
    recipients = set()

    # Adiciona os Telegram IDs dos gestores cadastrados
    for telegram_id, info in managers.items():
        if info.get("ativo", True):
            recipients.add(int(telegram_id))

    # Adiciona os Chat IDs dos grupos de gestores autorizados
    for chat_id_str in config.ALLOWED_CHAT_IDS:
        try:
            recipients.add(int(chat_id_str))
        except ValueError:
            pass

    if not recipients:
        logging.warning("⚠️ Nenhum gestor ou chat cadastrado para receber o prompt de relatório.")
        return

    data_texto = datetime.now().strftime("%d/%m/%Y às %H:%M")
    mensagem = (
        "📊 <b>RELATÓRIO DE MONITORAMENTO GLPI PRONTO</b>\n\n"
        f"🗓️ <b>Data:</b> {data_texto}\n\n"
        "Olá, gestor! O relatório executivo com os indicadores de chamados, "
        "carga da equipe e alertas de SLA está disponível.\n\n"
        "Deseja receber este relatório em formato HTML diretamente no seu <b>e-mail</b>?"
    )

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📧 Sim, enviar para meu e-mail", callback_data="confirm_email_send"),
            InlineKeyboardButton("❌ Agora não", callback_data="cancel_email_send")
        ]
    ])

    for chat_id in recipients:
        try:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=mensagem,
                reply_markup=teclado,
                parse_mode="HTML"
            )
            logging.info(f"Prompt de relatório enviado com sucesso para Chat ID: {chat_id}")
        except Exception as e:
            logging.error(f"Falha ao enviar prompt de relatório para Chat ID {chat_id}: {e}")


async def trigger_weekly_ranking(telegram_app: Application):
    """
    Envia automaticamente o ranking semanal para os gestores e grupos autorizados.
    """
    logging.info("🏆 Disparando ranking semanal automático para gestores no Telegram...")

    managers = config.get_managers_map()
    recipients = set()

    for telegram_id, info in managers.items():
        if info.get("ativo", True):
            recipients.add(int(telegram_id))

    for chat_id_str in config.ALLOWED_CHAT_IDS:
        try:
            recipients.add(int(chat_id_str))
        except ValueError:
            pass

    if not recipients:
        logging.warning("⚠️ Nenhum destinatário para o ranking semanal.")
        return

    try:
        ranking = await database.fetch_data(queries.SQL_RANKING_WEEKLY)
        msg = analytics_service.build_ranking_message(ranking)

        for chat_id in recipients:
            try:
                await telegram_app.bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode="HTML"
                )
                logging.info(f"Ranking semanal enviado para Chat ID: {chat_id}")
            except Exception as e:
                logging.error(f"Falha ao enviar ranking para Chat ID {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Erro ao gerar ranking semanal automático: {e}")


def _get_weekday_number(day_name: str) -> int:
    """Converte nome do dia da semana (inglês) para número (0=segunda, 6=domingo)."""
    days = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    return days.get(day_name.lower(), 0)


async def start_periodic_scheduler(telegram_app: Application):
    """Loop assíncrono do agendador em segundo plano (relatórios + ranking semanal)."""
    logging.info(f"⏰ Agendador de relatórios GLPI iniciado. Horários configurados: {config.SCHEDULE_TIMES}")
    logging.info(f"🏆 Ranking semanal configurado para: {config.RANKING_SCHEDULE_DAY} às {config.RANKING_SCHEDULE_TIME}")

    ranking_day = _get_weekday_number(config.RANKING_SCHEDULE_DAY)

    while True:
        now = datetime.now()

        # Próximo horário de relatório agendado
        proximo_relatorio = get_next_run(now)

        # Próximo horário de ranking semanal
        proximo_ranking = _get_next_ranking_run(now, ranking_day)

        # Pega o mais próximo entre relatório e ranking
        if proximo_ranking and proximo_ranking < proximo_relatorio:
            proximo = proximo_ranking
            tipo = "ranking"
        else:
            proximo = proximo_relatorio
            tipo = "relatorio"

        delta = (proximo - now).total_seconds()
        logging.info(
            f"Próximo disparo ({tipo}): {proximo.strftime('%Y-%m-%d %H:%M:%S')} "
            f"(em {int(delta)} segundos)"
        )

        await asyncio.sleep(max(1, delta))

        try:
            if tipo == "ranking":
                await trigger_weekly_ranking(telegram_app)
            else:
                await trigger_manager_report_prompt(telegram_app)
        except Exception as e:
            logging.error(f"Erro ao executar rotina do agendador ({tipo}): {e}")


def _get_next_ranking_run(now: datetime, target_weekday: int):
    """Calcula o próximo horário de disparo do ranking semanal."""
    try:
        parts = config.RANKING_SCHEDULE_TIME.split(":")
        h, m = int(parts[0]), int(parts[1])
    except Exception:
        h, m = 8, 0

    today = now.date()
    days_ahead = target_weekday - today.weekday()
    if days_ahead < 0:
        days_ahead += 7

    ranking_date = today + timedelta(days=days_ahead)
    ranking_dt = datetime.combine(ranking_date, time(h, m))

    # Se já passou nesta semana, pula para a próxima
    if ranking_dt <= now:
        ranking_dt += timedelta(days=7)

    return ranking_dt
