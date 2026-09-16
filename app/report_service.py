import logging
from typing import Dict, Any, Tuple
from app import database, queries, email_service, config


async def generate_and_send_manager_report(manager_name: str, manager_email: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Orquestra a busca de dados no banco do GLPI, compilação do relatório HTML
    e envio por e-mail para o gestor solicitante.
    """
    try:
        logging.info(f"Gerando dados do relatório GLPI para o gestor: {manager_name} ({manager_email})...")

        # Busca assíncrona dos dados
        kpis_raw = await database.fetch_data(queries.SQL_KPI_SUMMARY)
        kpis = kpis_raw[0] if kpis_raw else {}

        unassigned = await database.fetch_data(queries.SQL_UNASSIGNED_TICKETS)
        workload = await database.fetch_data(queries.SQL_WORKLOAD_PER_TECH)
        overdue = await database.fetch_data(queries.SQL_OVERDUE_TICKETS, params=(config.SLA_WARNING_HOURS,))
        inactive = await database.fetch_data(queries.SQL_INACTIVE_TICKETS, params=(config.INACTIVE_DAYS_THRESHOLD,))
        entity_metrics = await database.fetch_data(queries.SQL_METRICS_BY_ENTITY)

        # Compila HTML do E-mail
        html_body = email_service.build_html_report(
            manager_name=manager_name,
            kpis=kpis,
            unassigned_tickets=unassigned,
            workload=workload,
            overdue_tickets=overdue,
            inactive_tickets=inactive,
            entity_metrics=entity_metrics
        )

        subject = f"📊 Relatório GLPI - Monitoramento Executivo ({kpis.get('total_abertos', 0)} chamados abertos)"

        # Envia E-mail
        sucesso = await email_service.send_email_async(
            to_email=manager_email,
            subject=subject,
            html_body=html_body
        )

        metrics_summary = {
            "total_abertos": kpis.get("total_abertos", 0),
            "criados_hoje": kpis.get("criados_hoje", 0),
            "resolvidos_hoje": kpis.get("resolvidos_hoje", 0),
            "sem_tecnico": len(unassigned),
            "em_atraso_critico": len(overdue)
        }

        return sucesso, metrics_summary

    except Exception as e:
        logging.error(f"Erro ao gerar e enviar relatório para {manager_name}: {e}")
        return False, {}
