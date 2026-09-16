import asyncio
import logging
from pathlib import Path

from app.database import init_db_pool, close_db_pool
from app.bot import create_telegram_app
from app.scheduler import start_periodic_scheduler

# Configuração global de logs
logs_dir = Path(__file__).parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(logs_dir / "glpiBot_monitor.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

async def main():
    logging.info("🚀 Iniciando aplicação glpiBot_monitor (Relatórios Executivos & Monitoramento GLPI)...")

    # 1. Inicializa pool de banco de dados assíncrono
    await init_db_pool()

    # 2. Inicializa aplicação do Telegram Bot
    telegram_app = create_telegram_app()

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()

    # 3. Inicializa tarefas agendadas em segundo plano (Scheduler)
    tarefa_agendador = asyncio.create_task(start_periodic_scheduler(telegram_app))

    logging.info("✅ Sistema glpiBot_monitor em execução!")

    try:
        # Aguarda indefinidamente mantendo as corrotinas rodando
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Encerrando aplicação a pedido do usuário...")
    finally:
        logging.info("Finalizando serviços e conexões...")
        tarefa_agendador.cancel()
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
        await close_db_pool()
        logging.info("Encerrado com sucesso.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
