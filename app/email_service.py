import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Any

from app import config


def build_html_report(
    manager_name: str,
    kpis: Dict[str, Any],
    unassigned_tickets: List[Dict[str, Any]],
    workload: List[Dict[str, Any]],
    overdue_tickets: List[Dict[str, Any]],
    inactive_tickets: List[Dict[str, Any]],
    entity_metrics: List[Dict[str, Any]]
) -> str:
    """Gera o HTML responsivo e estilizado para o relatório executivo via e-mail."""
    data_hoje = datetime.now().strftime("%d/%m/%Y às %H:%M")

    # Renderização da Tabela: Sem Técnico
    rows_unassigned = ""
    if unassigned_tickets:
        for t in unassigned_tickets[:15]:
            rows_unassigned += f"""
            <tr>
                <td style="padding:10px; border-bottom:1px solid #eee; font-weight:bold; color:#0066cc;">#{t['id_chamado']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee;">{t['titulo']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee;">{t['unidade']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center;"><span style="background:#fff3cd; color:#856404; padding:3px 8px; border-radius:4px; font-weight:bold;">{t['dias_em_aberto']} dia(s)</span></td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center;">{t['prioridade']}</td>
            </tr>
            """
    else:
        rows_unassigned = '<tr><td colspan="5" style="padding:15px; text-align:center; color:#28a745;">✅ Nenhum chamado pendente de atribuição técnica.</td></tr>'

    # Renderização da Tabela: Carga por Técnico
    rows_workload = ""
    if workload:
        for w in workload:
            atraso_badge = f'<span style="background:#f8d7da; color:#721c24; padding:2px 6px; border-radius:4px; font-weight:bold;">{w["em_atraso"]}</span>' if w["em_atraso"] > 0 else "0"
            rows_workload += f"""
            <tr>
                <td style="padding:10px; border-bottom:1px solid #eee; font-weight:bold;">{w['tecnico']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center; font-weight:bold; color:#333;">{w['total_pendentes']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center;">{atraso_badge}</td>
            </tr>
            """
    else:
        rows_workload = '<tr><td colspan="3" style="padding:15px; text-align:center;">Nenhum dado disponível.</td></tr>'

    # Renderização da Tabela: Chamados em Atraso Crítico (> 48h)
    rows_overdue = ""
    if overdue_tickets:
        for o in overdue_tickets[:15]:
            rows_overdue += f"""
            <tr style="background-color:#fff5f5;">
                <td style="padding:10px; border-bottom:1px solid #fed7d7; font-weight:bold; color:#c53030;">#{o['id_chamado']}</td>
                <td style="padding:10px; border-bottom:1px solid #fed7d7;">{o['titulo']}</td>
                <td style="padding:10px; border-bottom:1px solid #fed7d7;">{o['tecnico']}</td>
                <td style="padding:10px; border-bottom:1px solid #fed7d7;">{o['unidade']}</td>
                <td style="padding:10px; border-bottom:1px solid #fed7d7; text-align:center; font-weight:bold; color:#c53030;">{o['horas_aberto']}h</td>
            </tr>
            """
    else:
        rows_overdue = '<tr><td colspan="5" style="padding:15px; text-align:center; color:#28a745;">🎉 Nenhum chamado crítico em atraso registrado!</td></tr>'

    # Renderização da Tabela: Chamados Sem Interação Recente
    rows_inactive = ""
    if inactive_tickets:
        for i in inactive_tickets[:15]:
            rows_inactive += f"""
            <tr>
                <td style="padding:10px; border-bottom:1px solid #eee; font-weight:bold; color:#d9534f;">#{i['id_chamado']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee;">{i['titulo']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee;">{i['tecnico']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee;">{i['unidade']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center;"><span style="background:#f8d7da; color:#721c24; padding:3px 8px; border-radius:4px; font-weight:bold;">{i['dias_sem_interacao']} dia(s)</span></td>
            </tr>
            """
    else:
        rows_inactive = '<tr><td colspan="5" style="padding:15px; text-align:center; color:#28a745;">✅ Nenhum chamado inativo sem interação recente registrado.</td></tr>'

    # Renderização da Tabela: Desempenho e Métricas por Unidade
    rows_entity = ""
    if entity_metrics:
        for e in entity_metrics[:15]:
            mttr_val = e.get('mttr_horas') or '0.0'
            rows_entity += f"""
            <tr>
                <td style="padding:10px; border-bottom:1px solid #eee; font-weight:bold;">{e['unidade']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center;">{e['total_geral']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center; font-weight:bold; color:#ff9900;">{e['abertos']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center; font-weight:bold; color:#28a745;">{e['resolvidos_hoje']}</td>
                <td style="padding:10px; border-bottom:1px solid #eee; text-align:center;">{mttr_val}h</td>
            </tr>
            """
    else:
        rows_entity = '<tr><td colspan="5" style="padding:15px; text-align:center;">Nenhum dado por unidade disponível.</td></tr>'

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
            .container {{ max-width: 800px; background: #ffffff; margin: 0 auto; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: #ffffff; padding: 25px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
            .header p {{ margin: 5px 0 0 0; opacity: 0.85; font-size: 14px; }}
            .content {{ padding: 30px; }}
            .kpi-grid {{ display: flex; justify-content: space-between; margin-bottom: 30px; gap: 10px; }}
            .kpi-card {{ flex: 1; background: #f8f9fa; border-left: 4px solid #2a5298; border-radius: 6px; padding: 15px; text-align: center; }}
            .kpi-card.warning {{ border-left-color: #ff9900; }}
            .kpi-card.danger {{ border-left-color: #d9534f; }}
            .kpi-card.success {{ border-left-color: #28a745; }}
            .kpi-value {{ font-size: 26px; font-weight: bold; color: #111; margin-top: 5px; }}
            .kpi-label {{ font-size: 12px; color: #666; text-transform: uppercase; font-weight: 600; }}
            .section-title {{ font-size: 18px; color: #1e3c72; border-bottom: 2px solid #eef2f5; padding-bottom: 8px; margin-top: 30px; margin-bottom: 15px; font-weight: 600; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px; }}
            th {{ background-color: #eef2f7; color: #495057; text-align: left; padding: 10px; font-weight: 600; border-bottom: 2px solid #dee2e6; }}
            .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #eee; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Relatório Executivo GLPI</h1>
                <p>Gerado para <strong>{manager_name}</strong> em {data_hoje}</p>
            </div>
            <div class="content">
                <!-- KPI GRID -->
                <div class="kpi-grid">
                    <div class="kpi-card warning">
                        <div class="kpi-label">Total Abertos</div>
                        <div class="kpi-value">{kpis.get('total_abertos', 0)}</div>
                    </div>
                    <div class="kpi-card success">
                        <div class="kpi-label">Criados Hoje</div>
                        <div class="kpi-value">{kpis.get('criados_hoje', 0)}</div>
                    </div>
                    <div class="kpi-card success">
                        <div class="kpi-label">Resolvidos Hoje</div>
                        <div class="kpi-value">{kpis.get('resolvidos_hoje', 0)}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">MTTR Hoje</div>
                        <div class="kpi-value">{kpis.get('mttr_hoje_horas') or '0.0'}h</div>
                    </div>
                </div>

                <!-- SEÇÃO 1: CHAMADOS SEM TÉCNICO -->
                <div class="section-title">⚠️ Chamados Sem Técnico Atribuído ({len(unassigned_tickets)})</div>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Título</th>
                            <th>Unidade</th>
                            <th style="text-align:center;">Dias Aberto</th>
                            <th style="text-align:center;">Prioridade</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_unassigned}
                    </tbody>
                </table>

                <!-- SEÇÃO 2: CHAMADOS CRÍTICOS EM ATRASO (> 48h) -->
                <div class="section-title">🚨 Chamados Críticos em Atraso (&gt; {config.SLA_WARNING_HOURS}h)</div>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Título</th>
                            <th>Técnico</th>
                            <th>Unidade</th>
                            <th style="text-align:center;">Horas Aberto</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_overdue}
                    </tbody>
                </table>

                <!-- SEÇÃO 3: DISTRIBUIÇÃO DA CARGA DE TRABALHO POR TÉCNICO -->
                <div class="section-title">👥 Distribuição de Carga de Trabalho por Técnico</div>
                <table>
                    <thead>
                        <tr>
                            <th>Técnico</th>
                            <th style="text-align:center;">Total Pendentes</th>
                            <th style="text-align:center;">Em Atraso (&gt;2d)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_workload}
                    </tbody>
                </table>

                <!-- SEÇÃO 4: CHAMADOS SEM INTERAÇÃO RECENTE -->
                <div class="section-title">⌛ Chamados Sem Interação Recente (&gt; {config.INACTIVE_DAYS_THRESHOLD} dias)</div>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Título</th>
                            <th>Técnico</th>
                            <th>Unidade</th>
                            <th style="text-align:center;">Sem Modificação</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_inactive}
                    </tbody>
                </table>

                <!-- SEÇÃO 5: DESEMPENHO E MÉTRICAS POR UNIDADE -->
                <div class="section-title">🏢 Desempenho e Métricas por Unidade</div>
                <table>
                    <thead>
                        <tr>
                            <th>Unidade</th>
                            <th style="text-align:center;">Total Geral</th>
                            <th style="text-align:center;">Abertos</th>
                            <th style="text-align:center;">Resolvidos Hoje</th>
                            <th style="text-align:center;">MTTR Médio</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_entity}
                    </tbody>
                </table>
            </div>
            <div class="footer">
                <p>Este relatório foi gerado automaticamente pelo sistema <strong>glpiBot_monitor</strong>.<br>
                Uso exclusivo para fins de monitoramento e gestão da equipe de suporte.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content


async def send_email_async(
    to_email: str,
    subject: str,
    html_body: str
) -> bool:
    """Envia o e-mail formatado em HTML para o endereço do gestor."""
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        logging.error("❌ Credenciais de SMTP não configuradas no .env!")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{config.SMTP_FROM_NAME} <{config.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Tenta usar aiosmtplib se instalado
    try:
        import aiosmtplib
        await aiosmtplib.send(
            msg,
            hostname=config.SMTP_SERVER,
            port=config.SMTP_PORT,
            username=config.SMTP_USER,
            password=config.SMTP_PASSWORD,
            use_tls=config.SMTP_USE_TLS and config.SMTP_PORT == 465,
            start_tls=config.SMTP_USE_TLS and config.SMTP_PORT == 587
        )
        logging.info(f"✅ E-mail enviado com sucesso via aiosmtplib para: {to_email}")
        return True
    except ImportError:
        pass
    except Exception as e:
        logging.error(f"Erro no envio via aiosmtplib: {e}")

    # Fallback usando smtplib síncrono no executor do asyncio
    def _sync_send():
        try:
            if config.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=15)
            else:
                server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=15)
                if config.SMTP_USE_TLS:
                    server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM_EMAIL, [to_email], msg.as_string())
            server.quit()
            return True
        except Exception as err:
            logging.error(f"❌ Falha no envio de e-mail (smtplib fallback) para {to_email}: {err}")
            return False

    return await asyncio.to_thread(_sync_send)
