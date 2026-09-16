import asyncio
import logging
from typing import List, Dict, Any, Optional

from app import config

_pool = None

async def init_db_pool():
    """Inicializa o pool de conexões assíncronas MySQL."""
    global _pool
    try:
        import aiomysql
        _pool = await aiomysql.create_pool(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            db=config.DB_NAME,
            charset='utf8mb4',
            cursorclass=aiomysql.DictCursor,
            minsize=1,
            maxsize=10,
            autocommit=True
        )
        logging.info("✅ Pool de conexões MySQL (aiomysql) inicializado com sucesso.")
    except ImportError:
        logging.warning("⚠️ Biblioteca aiomysql não instalada. Usando conector assíncrono via executor thread pool.")
        _pool = None
    except Exception as e:
        logging.error(f"❌ Erro ao inicializar pool de conexões MySQL: {e}")
        _pool = None

async def close_db_pool():
    """Encerra o pool de conexões ao desligar o sistema."""
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        logging.info("Pool de conexões MySQL encerrado.")

async def fetch_data(query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """Executa consultas SELECT de forma assíncrona e retorna lista de dicionários."""
    global _pool
    params = params or ()

    # Tenta utilizar o pool aiomysql se disponível
    if _pool is not None:
        try:
            async with _pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    result = await cursor.fetchall()
                    return result or []
        except Exception as e:
            logging.error(f"Erro na execução da consulta MySQL (aiomysql): {e}")

    # Fallback assíncrono usando executor em thread pool (com mysql-connector-python)
    def _sync_fetch():
        import mysql.connector
        conn = None
        try:
            conn = mysql.connector.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            result = cursor.fetchall()
            cursor.close()
            return result or []
        except Exception as err:
            logging.error(f"Erro na consulta MySQL (sync fallback): {err}")
            return []
        finally:
            if conn and conn.is_connected():
                conn.close()

    return await asyncio.to_thread(_sync_fetch)
