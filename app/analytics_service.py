import logging
from typing import List, Dict, Any
from datetime import datetime

from app import config


def build_tech_performance_message(
    performance: List[Dict[str, Any]],
    rejected_per_tech: List[Dict[str, Any]]
) -> str:
    """
    Monta a mensagem Telegram com performance individual de cada técnico.
    Inclui: resolvidos hoje, MTTR corrido e soluções rejeitadas com alertas automáticos.
    """
    if not performance:
        return (
            "👨🔧 <b>PERFORMANCE DOS TÉCNICOS — HOJE</b>\n\n"
            "ℹ️ Nenhum técnico resolveu chamados até o momento hoje."
        )

    # Mapeia rejeições por técnico para cruzamento rápido
    rejeicoes_map = {r["tecnico"]: r["total_solucoes_recusadas"] for r in rejected_per_tech} if rejected_per_tech else {}

    linhas = []
    tecnicos_com_alerta = []

    for tech in performance:
        nome = tech["tecnico"]
        resolvidos = tech["resolvidos_hoje"]
        mttr = tech.get("mttr_corrido_horas") or 0
        rejeicoes = rejeicoes_map.get(nome, 0)

        bloco = f"<b>{nome}:</b>\n"
        bloco += f"  ✔️ Resolvidos: <code>{resolvidos}</code>\n"

        # Alerta de MTTR alto
        mttr_threshold = getattr(config, "MTTR_HIGH_THRESHOLD_HOURS", 24)
        if mttr and float(mttr) >= mttr_threshold:
            bloco += f"  ⚠️ MTTR alto: <code>{mttr}h</code>\n"
        else:
            bloco += f"  ⏱️ Tempo médio: <code>{mttr}h</code>\n"

        # Alerta de soluções rejeitadas
        if rejeicoes > 0:
            bloco += f"  🔥 {rejeicoes} solução(ões) rejeitada(s)\n"
            tecnicos_com_alerta.append(nome)

        linhas.append(bloco)

    msg = "👨🔧 <b>PERFORMANCE DOS TÉCNICOS — HOJE</b>\n\n"
    msg += "\n".join(linhas)

    # Ação recomendada
    if tecnicos_com_alerta:
        nomes_alerta = ", ".join(tecnicos_com_alerta)
        msg += f"\n👉 <b>Ação recomendada:</b>\nRevisar qualidade de atendimento: {nomes_alerta}"

    return msg


def build_insights_message(
    category_trend: List[Dict[str, Any]],
    entity_trend: List[Dict[str, Any]]
) -> str:
    """
    Detecta categorias com variação significativa e identifica as unidades mais impactadas.
    Gera recomendações automáticas baseadas em regras.
    """
    insight_threshold = getattr(config, "INSIGHT_VARIATION_THRESHOLD", 20)

    # Mapa de unidade mais impactada por categoria (vem da query com CTE)
    entity_map = {}
    if entity_trend:
        for e in entity_trend:
            entity_map[e["categoria"]] = {
                "unidade": e["unidade_mais_impactada"],
                "total": e.get("total_recente", 0),
                "qtd_recente": e.get("qtd_recente", 0),
                "qtd_anterior": e.get("qtd_anterior", 0),
            }

    insights = []

    if category_trend:
        for cat in category_trend:
            categoria = cat["categoria"]
            qtd_recente = cat.get("qtd_recente", 0) or 0
            qtd_anterior = cat.get("qtd_anterior", 0) or 0

            # Calcula variação percentual
            if qtd_anterior > 0:
                variacao = ((qtd_recente - qtd_anterior) / qtd_anterior) * 100
            elif qtd_recente > 0:
                variacao = 100.0
            else:
                continue

            if variacao < insight_threshold:
                continue

            bloco = f"📈 <b>Categoria: {categoria}</b>\n"
            bloco += f"Aumento de <b>+{variacao:.0f}%</b> nos últimos 3 dias "
            bloco += f"(<code>{qtd_anterior}</code> → <code>{qtd_recente}</code> tickets)\n"

            # Unidade mais impactada
            entity_info = entity_map.get(categoria)
            if entity_info:
                bloco += f"\n🏢 <b>Unidade mais impactada:</b> {entity_info['unidade']}\n"

            # Recomendação baseada em regras
            recomendacao = _gerar_recomendacao(categoria)
            bloco += f"\n👉 <b>Possível causa:</b>\n{recomendacao['causa']}\n"
            bloco += f"\n👉 <b>Recomendação:</b>\n{recomendacao['acao']}"

            insights.append(bloco)

    if not insights:
        return (
            "🧠 <b>INSIGHT AUTOMÁTICO</b>\n\n"
            "✅ Nenhuma tendência significativa de alta detectada nos últimos 3 dias.\n"
            "As categorias de chamados estão estáveis."
        )

    msg = "🧠 <b>INSIGHT AUTOMÁTICO</b>\n\n"
    msg += "\n\n━━━━━━━━━━━━━━━━━━━━━\n\n".join(insights)

    return msg


def _gerar_recomendacao(categoria: str) -> Dict[str, str]:
    """Gera causa provável e ação recomendada com base na categoria."""
    cat_lower = categoria.lower()

    regras = {
        "infraestrutura": {
            "causa": "Problemas recorrentes de rede ou infraestrutura física",
            "acao": "Abrir análise preventiva e verificar logs de infraestrutura"
        },
        "rede": {
            "causa": "Instabilidade ou saturação de links de rede",
            "acao": "Verificar switches, firewalls e monitoramento de tráfego"
        },
        "software": {
            "causa": "Possível impacto de atualização ou deploy recente",
            "acao": "Verificar changelog de sistemas e possíveis rollbacks"
        },
        "hardware": {
            "causa": "Aumento de falhas em equipamentos (possível lote defeituoso ou vida útil)",
            "acao": "Avaliar substituição preventiva e inventário de ativos"
        },
        "acesso": {
            "causa": "Possível falha em serviço de autenticação (AD/LDAP) ou políticas de grupo",
            "acao": "Verificar integridade dos serviços de diretório"
        },
        "impressora": {
            "causa": "Problemas recorrentes de impressão (drivers, rede ou hardware)",
            "acao": "Verificar servidor de impressão e fila de impressoras"
        },
        "e-mail": {
            "causa": "Possível problema no servidor de e-mail ou regras de spam",
            "acao": "Verificar filas de entrega e logs do servidor de e-mail"
        },
    }

    for chave, rec in regras.items():
        if chave in cat_lower:
            return rec

    return {
        "causa": f"Aumento atípico de demanda na categoria '{categoria}'",
        "acao": "Abrir análise preventiva para investigar a causa raiz"
    }


def build_ranking_message(ranking: List[Dict[str, Any]]) -> str:
    """
    Monta o ranking semanal com medalhas e destaque de menor MTTR.
    """
    now = datetime.now()
    semana_num = now.isocalendar()[1]
    ano = now.year

    if not ranking:
        return (
            f"🏆 <b>RANKING DA SEMANA</b> (Semana {semana_num}/{ano})\n\n"
            "ℹ️ Nenhum técnico resolveu chamados nesta semana ainda."
        )

    medalhas = ["🥇", "🥈", "🥉"]
    linhas = []
    total_equipe = 0
    menor_mttr_nome = None
    menor_mttr_valor = float('inf')

    for i, tech in enumerate(ranking):
        nome = tech["tecnico"]
        resolvidos = tech["resolvidos_semana"]
        mttr = tech.get("mttr_corrido_horas") or 0
        total_equipe += resolvidos

        medalha = medalhas[i] if i < len(medalhas) else f"  {i + 1}º"
        linhas.append(f"{medalha} <b>{nome}</b> — {resolvidos} tickets (MTTR: {mttr}h)")

        # Rastrear menor MTTR (excluindo zeros e nulos)
        if mttr and float(mttr) > 0 and float(mttr) < menor_mttr_valor:
            menor_mttr_valor = float(mttr)
            menor_mttr_nome = nome

    msg = f"🏆 <b>RANKING DA SEMANA</b> (Semana {semana_num}/{ano})\n\n"
    msg += "\n".join(linhas)

    if menor_mttr_nome:
        msg += f"\n\n🔥 <b>Destaque:</b> menor tempo médio → <b>{menor_mttr_nome}</b> ({menor_mttr_valor}h)"

    msg += f"\n\n📊 <b>Total da equipe:</b> {total_equipe} tickets resolvidos"

    return msg


def build_rejected_detail_message(rejected_detail: List[Dict[str, Any]]) -> str:
    """
    Monta mensagem com os últimos chamados com solução rejeitada.
    """
    if not rejected_detail:
        return (
            "❌ <b>SOLUÇÕES REJEITADAS</b>\n\n"
            "✅ Nenhuma solução rejeitada registrada."
        )

    msg = "❌ <b>SOLUÇÕES REJEITADAS (RECENTES)</b>\n\n"

    for item in rejected_detail[:10]:
        chamado = item.get("chamado", "?")
        titulo = item.get("titulo", "Sem título")
        tecnico = item.get("tecnico_autor_solucao", "NÃO ATRIBUÍDO")
        unidade = item.get("nome_unidade", "NÃO INFORMADO")
        data_rej = item.get("data_rejeicao", "")

        if data_rej and hasattr(data_rej, 'strftime'):
            data_rej = data_rej.strftime("%d/%m/%Y %H:%M")

        msg += (
            f"🔸 <b>#{chamado}</b> — {titulo}\n"
            f"   👤 Técnico: {tecnico}\n"
            f"   🏢 Unidade: {unidade}\n"
            f"   📅 Rejeitada em: {data_rej}\n\n"
        )

    return msg
