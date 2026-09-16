import logging
from typing import Optional, Dict
from telegram import Update
from telegram.ext import ContextTypes
from app import config


def is_manager_authorized(user_id: int, chat_id: Optional[int] = None) -> bool:
    """
    Verifica se o usuário do Telegram é um Gestor cadastrado e ativo em managers.json
    ou se o chat pertence aos chat IDs autorizados.
    """
    user_id_str = str(user_id)
    managers = config.get_managers_map()

    # Se estiver cadastrado no managers.json e ativo
    if user_id_str in managers and managers[user_id_str].get("ativo", True):
        return True

    # Se o chat_id estiver na lista de chats autorizados
    if chat_id and str(chat_id) in config.ALLOWED_CHAT_IDS:
        return True

    return False


def get_manager_info(user_id: int) -> Optional[Dict]:
    """Retorna o perfil cadastrado do gestor (nome, e-mail, cargo) pelo Telegram ID."""
    user_id_str = str(user_id)
    managers = config.get_managers_map()
    return managers.get(user_id_str)


async def manager_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Middleware / Gate de segurança para os handlers do Telegram.
    Bloqueia e notifica caso um usuário não autorizado tente usar o bot de gestores.
    """
    user = update.effective_user
    chat = update.effective_chat

    if not user:
        return False

    if is_manager_authorized(user.id, chat.id if chat else None):
        return True

    logging.warning(
        f"Acesso negado | Usuário Telegram ID: {user.id} (@{user.username or 'sem_username'}) | "
        f"Nome: {user.full_name}"
    )

    msg_recusa = (
        "🔒 <b>Acesso Restrito</b>\n\n"
        "Este bot é exclusivo para <b>Gestores e Coordenadores de TI</b>.\n"
        "Seu perfil do Telegram não possui permissão para visualizar relatórios ou emitir comandos.\n\n"
        "Caso você seja um gestor, solicite o cadastro do seu Telegram ID ao administrador do sistema."
    )

    if update.message:
        await update.message.reply_text(msg_recusa, parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.answer("Acesso restrito a gestores.", show_alert=True)

    return False
