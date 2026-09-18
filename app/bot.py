import html
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    Application,
    ContextTypes
)

from app import config, security, database, queries, report_service, analytics_service


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe a mensagem de boas-vindas e comandos exclusivos para Gestores."""
    if not await security.manager_gate(update, context):
        return

    user = update.effective_user
    manager_info = security.get_manager_info(user.id)
    email_cadastrado = manager_info.get("email") if manager_info else "Não cadastrado"

    user_name = html.escape(user.first_name) if user and user.first_name else "Gestor"

    msg = (
        f"👔 <b>Painel de Gestão GLPI Monitor</b>\n"
        f"Olá, <b>{user_name}</b>! Seus privilégios de gestor foram confirmados.\n\n"
        f"📧 <b>E-mail de destino cadastrado:</b> <code>{email_cadastrado}</code>\n\n"
        "<b>Comandos Disponíveis para Gestores:</b>\n"
        "• /relatorio — Solicita o relatório executivo em HTML por e-mail\n"
        "• /status — Visualiza métricas rápidas de KPIs no Telegram\n"
        "• /performance — Performance dos técnicos hoje (MTTR + rejeições)\n"
        "• /insights — Insights automáticos de tendências de categorias\n"
        "• /ranking — Ranking semanal da equipe com gamificação\n"
        "• /cadastrar_email <code>seu.email@empresa.com</code> — Atualiza seu e-mail de destino\n"
        "• /help — Guia de utilização e suporte\n"
    )

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Solicitar Relatório por E-mail", callback_data="confirm_email_send")],
        [InlineKeyboardButton("📈 Métricas Rápidas (/status)", callback_data="quick_status")],
        [InlineKeyboardButton("👨🔧 Performance Técnicos", callback_data="quick_performance")],
        [InlineKeyboardButton("🧠 Insights", callback_data="quick_insights"),
         InlineKeyboardButton("🏆 Ranking", callback_data="quick_ranking")]
    ])

    await update.message.reply_text(msg, reply_markup=teclado, parse_mode="HTML")


async def relatorio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oferece o botão interativo para o gestor confirmar se quer enviar o relatório para seu e-mail."""
    if not await security.manager_gate(update, context):
        return

    user = update.effective_user
    manager_info = security.get_manager_info(user.id)
    email_dest = manager_info.get("email") if manager_info else None

    if not email_dest:
        msg_sem_email = (
            "⚠️ <b>E-mail não cadastrado</b>\n\n"
            "Seu perfil do Telegram ainda não possui um e-mail de destino associado.\n"
            "Por favor, digite o comando abaixo para cadastrar seu e-mail:\n"
            "<code>/cadastrar_email seu.email@empresa.com.br</code>"
        )
        await update.message.reply_text(msg_sem_email, parse_mode="HTML")
        return

    full_name = html.escape(user.full_name) if user else "Gestor"

    msg = (
        "📋 <b>SOLICITAÇÃO DE RELATÓRIO EXECUTIVO</b>\n\n"
        f"Gestor: <b>{full_name}</b>\n"
        f"E-mail de destino: <code>{email_dest}</code>\n\n"
        "Deseja gerar o relatório de monitoramento atualizado e enviá-lo para o seu e-mail?"
    )

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📧 Sim, enviar para meu e-mail", callback_data="confirm_email_send"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_email_send")
        ]
    ])

    await update.message.reply_text(msg, reply_markup=teclado, parse_mode="HTML")


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe métricas rápidas no Telegram sem enviar e-mail."""
    if not await security.manager_gate(update, context):
        return

    chat_id = update.effective_chat.id
    msg_carregando = await context.bot.send_message(chat_id=chat_id, text="🔍 Consultando dados no GLPI...")

    try:
        kpis_raw = await database.fetch_data(queries.SQL_KPI_SUMMARY)
        kpis = kpis_raw[0] if kpis_raw else {}
        unassigned = await database.fetch_data(queries.SQL_UNASSIGNED_TICKETS)
        overdue = await database.fetch_data(queries.SQL_OVERDUE_TICKETS, params=(config.SLA_WARNING_HOURS,))

        total_abertos = kpis.get("total_abertos", 0)
        criados_hoje = kpis.get("criados_hoje", 0)
        resolvidos_hoje = kpis.get("resolvidos_hoje", 0)
        mttr = kpis.get("mttr_hoje_horas") or "0.0"

        msg = (
            "📊 <b>RESUMO EXECUTIVO RÁPIDO DO GLPI</b>\n\n"
            f"🟡 <b>Total Abertos:</b> <code>{total_abertos}</code>\n"
            f"🟢 <b>Criados Hoje:</b> <code>{criados_hoje}</code>\n"
            f"✅ <b>Resolvidos Hoje:</b> <code>{resolvidos_hoje}</code>\n"
            f"⏱️ <b>MTTR Hoje:</b> <code>{mttr}h</code>\n\n"
            f"⚠️ <b>Chamados Sem Técnico:</b> <code>{len(unassigned)}</code>\n"
            f"🚨 <b>Atraso Crítico (> {config.SLA_WARNING_HOURS}h):</b> <code>{len(overdue)}</code>\n\n"
            "Deseja receber a versão completa detalhada em HTML por e-mail?"
        )

        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("📧 Sim, enviar relatório por e-mail", callback_data="confirm_email_send")]
        ])

        await msg_carregando.edit_text(msg, reply_markup=teclado, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Erro ao consultar status rápido: {e}")
        await msg_carregando.edit_text("❌ Falha ao consultar o banco de dados do GLPI.")


async def performance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe a performance dos técnicos no dia atual (resolvidos, MTTR, soluções rejeitadas)."""
    if not await security.manager_gate(update, context):
        return

    chat_id = update.effective_chat.id
    msg_carregando = await context.bot.send_message(chat_id=chat_id, text="🔍 Analisando performance dos técnicos...")

    try:
        performance = await database.fetch_data(queries.SQL_TECH_PERFORMANCE_TODAY)
        rejected = await database.fetch_data(queries.SQL_REJECTED_SOLUTIONS_PER_TECH)

        msg = analytics_service.build_tech_performance_message(performance, rejected)
        await msg_carregando.edit_text(msg, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Erro ao consultar performance dos técnicos: {e}")
        await msg_carregando.edit_text("❌ Falha ao consultar dados de performance.")


async def insights_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe insights automáticos de tendências de categorias de chamados."""
    if not await security.manager_gate(update, context):
        return

    chat_id = update.effective_chat.id
    msg_carregando = await context.bot.send_message(chat_id=chat_id, text="🧠 Gerando insights automáticos...")

    try:
        category_trend = await database.fetch_data(queries.SQL_CATEGORY_TREND)
        entity_trend = await database.fetch_data(queries.SQL_ENTITY_TREND)

        msg = analytics_service.build_insights_message(category_trend, entity_trend)
        await msg_carregando.edit_text(msg, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Erro ao gerar insights automáticos: {e}")
        await msg_carregando.edit_text("❌ Falha ao gerar insights automáticos.")


async def ranking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o ranking semanal de técnicos com gamificação."""
    if not await security.manager_gate(update, context):
        return

    chat_id = update.effective_chat.id
    msg_carregando = await context.bot.send_message(chat_id=chat_id, text="🏆 Gerando ranking da semana...")

    try:
        ranking = await database.fetch_data(queries.SQL_RANKING_WEEKLY)

        msg = analytics_service.build_ranking_message(ranking)
        await msg_carregando.edit_text(msg, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Erro ao gerar ranking semanal: {e}")
        await msg_carregando.edit_text("❌ Falha ao gerar ranking semanal.")



async def cadastrar_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite ao gestor vincular ou atualizar seu endereço de e-mail."""
    if not await security.manager_gate(update, context):
        return

    user = update.effective_user
    args = context.args

    if not args or "@" not in args[0]:
        await update.message.reply_text(
            "❗ <b>Uso correto:</b> <code>/cadastrar_email seu.email@empresa.com.br</code>",
            parse_mode="HTML"
        )
        return

    novo_email = args[0].strip().lower()
    user_id_str = str(user.id)

    managers = config.get_managers_map()
    if user_id_str not in managers:
        managers[user_id_str] = {
            "nome": user.full_name,
            "email": novo_email,
            "cargo": "Gestor",
            "ativo": True
        }
    else:
        managers[user_id_str]["email"] = novo_email

    if config.save_managers_map(managers):
        await update.message.reply_text(
            f"✅ <b>E-mail atualizado com sucesso!</b>\n\n"
            f"Endereço cadastrado: <code>{novo_email}</code>\n"
            "Agora você pode solicitar relatórios via <code>/relatorio</code>.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ Falha ao salvar configuração do gestor no servidor.")


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trata os cliques nos botões de confirmação de envio por e-mail."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    if not security.is_manager_authorized(user.id, update.effective_chat.id if update.effective_chat else None):
        await query.answer("Acesso exclusivo para gestores autorizados.", show_alert=True)
        return

    if data == "cancel_email_send":
        try:
            await query.edit_message_text("❌ Operação de envio por e-mail cancelada pelo gestor.")
        except Exception:
            pass
        return

    if data == "quick_status":
        await status_handler(update, context)
        return

    if data == "quick_performance":
        await performance_handler(update, context)
        return

    if data == "quick_insights":
        await insights_handler(update, context)
        return

    if data == "quick_ranking":
        await ranking_handler(update, context)
        return

    if data == "confirm_email_send":
        manager_info = security.get_manager_info(user.id)
        email_dest = manager_info.get("email") if manager_info else None

        if not email_dest:
            msg_erro = (
                "⚠️ <b>E-mail não encontrado!</b>\n\n"
                "Utilize o comando abaixo para cadastrar seu e-mail antes de solicitar:\n"
                "<code>/cadastrar_email seu.email@empresa.com.br</code>"
            )
            try:
                await query.edit_message_text(msg_erro, parse_mode="HTML")
            except Exception:
                pass
            return

        try:
            await query.edit_message_text(
                f"⏳ <b>Gerando relatório GLPI...</b>\n"
                f"Destinatário: <code>{email_dest}</code>\n"
                "Por favor, aguarde alguns instantes...",
                parse_mode="HTML"
            )
        except Exception:
            pass

        # Dispara orquestrador de envio de relatório
        sucesso, metrics = await report_service.generate_and_send_manager_report(
            manager_name=user.full_name,
            manager_email=email_dest
        )

        full_name = html.escape(user.full_name) if user else "Gestor"

        if sucesso:
            msg_sucesso = (
                f"✅ <b>RELATÓRIO ENVIADO COM SUCESSO!</b>\n\n"
                f"👤 <b>Gestor:</b> {full_name}\n"
                f"📧 <b>Enviado para:</b> <code>{email_dest}</code>\n\n"
                f"📊 <b>Resumo Enviado:</b>\n"
                f"• Total Abertos: <code>{metrics.get('total_abertos', 0)}</code>\n"
                f"• Sem Técnico: <code>{metrics.get('sem_tecnico', 0)}</code>\n"
                f"• Em Atraso Crítico: <code>{metrics.get('em_atraso_critico', 0)}</code>\n\n"
                "Verifique a caixa de entrada (ou de spam) do seu e-mail."
            )
            try:
                await query.edit_message_text(msg_sucesso, parse_mode="HTML")
            except Exception:
                pass
        else:
            msg_falha = (
                f"❌ <b>FALHA NO ENVIO DO E-MAIL</b>\n\n"
                f"Não foi possível entregar o e-mail para <code>{email_dest}</code>.\n"
                "Verifique se as credenciais de SMTP no arquivo <code>.env</code> estão corretas."
            )
            try:
                await query.edit_message_text(msg_falha, parse_mode="HTML")
            except Exception:
                pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handler global de exceções não tratadas nos comandos do Telegram Bot."""
    logging.error(f"⚠️ Exceção no Telegram Bot ao processar update: {context.error}")


def create_telegram_app() -> Application:
    """Cria e configura a aplicação python-telegram-bot."""
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN não foi configurado no arquivo .env!")

    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # Registro de handlers de erro e comandos
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("menu", start_handler))
    app.add_handler(CommandHandler("help", start_handler))
    app.add_handler(CommandHandler("relatorio", relatorio_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("cadastrar_email", cadastrar_email_handler))
    app.add_handler(CommandHandler("performance", performance_handler))
    app.add_handler(CommandHandler("insights", insights_handler))
    app.add_handler(CommandHandler("ranking", ranking_handler))

    # Handlers de botões inline
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    logging.info("🤖 Aplicação Telegram Bot configurada com handlers executivos em HTML.")
    return app
