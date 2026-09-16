import asyncio
import logging
from datetime import datetime, time, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application

from app import config


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


async def start_periodic_scheduler(telegram_app: Application):
    """Loop assíncrono do agendador em segundo plano."""
    logging.info(f"⏰ Agendador de relatórios GLPI iniciado. Horários configurados: {config.SCHEDULE_TIMES}")

    while True:
        now = datetime.now()
        proximo = get_next_run(now)
        delta = (proximo - now).total_seconds()

        logging.info(f"Próximo alerta de relatório agendado para: {proximo.strftime('%Y-%m-%d %H:%M:%S')} (em {int(delta)} segundos)")

        await asyncio.sleep(max(1, delta))

        try:
            await trigger_manager_report_prompt(telegram_app)
        except Exception as e:
            logging.error(f"Erro ao executar rotina do agendador: {e}")
