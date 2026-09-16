import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Carrega arquivo .env na raiz do projeto (um nível acima de app/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ===== CONFIGURAÇÕES DO TELEGRAM BOT =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ALLOWED_CHAT_IDS_RAW = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS = [
    chat_id.strip() for chat_id in ALLOWED_CHAT_IDS_RAW.split(",") if chat_id.strip()
]

# ===== CONFIGURAÇÕES DO BANCO DE DADOS GLPI (READ-ONLY) =====
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "glpi")

# ===== CONFIGURAÇÕES DE SMTP (ENVIO DE E-MAIL) =====
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "GLPI Monitoria Executiva")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USER)
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "True").lower() in ("true", "1", "t", "yes")

# ===== PARAMETROS DE GESTÃO DE MONITORAMENTO =====
SCHEDULE_TIMES_RAW = os.getenv("SCHEDULE_TIMES", "07:30,18:00")
SCHEDULE_TIMES = [
    t.strip() for t in SCHEDULE_TIMES_RAW.split(",") if t.strip()
]
SLA_WARNING_HOURS = int(os.getenv("SLA_WARNING_HOURS", 48))
INACTIVE_DAYS_THRESHOLD = int(os.getenv("INACTIVE_DAYS_THRESHOLD", 7))

# ===== CARREGAMENTO DO MAPEAMENTO DE GESTORES =====
MANAGERS_FILE = BASE_DIR / "managers.json"

def get_managers_map() -> dict:
    """Carrega dinamicamente o dicionário de gestores cadastrados."""
    if not MANAGERS_FILE.exists():
        logging.warning("Arquivo managers.json não encontrado. Criando modelo vazio...")
        return {}
    try:
        with open(MANAGERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar managers.json: {e}")
        return {}

def save_managers_map(data: dict) -> bool:
    """Salva atualização do mapeamento de gestores no arquivo managers.json."""
    try:
        with open(MANAGERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar managers.json: {e}")
        return False
