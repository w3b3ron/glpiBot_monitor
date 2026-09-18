# ==============================================================================
# CONSULTAS SQL PARA MONITORIA E GESTÃO EXECUTIVA DO GLPI (READ-ONLY)
# ==============================================================================

# 1. KPI Resumo do Dia e Status Geral
SQL_KPI_SUMMARY = """
SELECT 
    COUNT(CASE WHEN gt.is_deleted = 0 AND gt.status NOT IN (5, 6) THEN 1 END) AS total_abertos,
    COUNT(CASE WHEN gt.is_deleted = 0 AND DATE(gt.date_creation) = CURDATE() THEN 1 END) AS criados_hoje,
    COUNT(CASE WHEN gt.is_deleted = 0 AND DATE(gt.solvedate) = CURDATE() THEN 1 END) AS resolvidos_hoje,
    ROUND(AVG(CASE WHEN gt.is_deleted = 0 AND gt.solvedate IS NOT NULL AND DATE(gt.solvedate) = CURDATE() 
              THEN TIMESTAMPDIFF(SECOND, gt.date_creation, gt.solvedate)/3600 END), 1) AS mttr_hoje_horas
FROM glpi_tickets gt;
"""

# 2. Chamados Sem Técnico Atribuído (Gargalo de Delegação)
SQL_UNASSIGNED_TICKETS = """
SELECT 
    gt.id AS id_chamado,
    UPPER(gt.name) AS titulo,
    UPPER(COALESCE(ge.name, 'NÃO INFORMADO')) AS unidade,
    gt.date_creation AS dt_abertura,
    DATEDIFF(CURDATE(), gt.date_creation) AS dias_em_aberto,
    UPPER(CASE gt.priority
        WHEN 2 THEN 'Baixa'
        WHEN 3 THEN 'Média'
        WHEN 4 THEN 'Alta'
        WHEN 5 THEN 'Muito Alta'
        ELSE 'Normal'
    END) AS prioridade
FROM glpi_tickets gt
LEFT JOIN glpi_entities ge ON gt.entities_id = ge.id
LEFT JOIN glpi_tickets_users gtu ON gt.id = gtu.tickets_id AND gtu.type = 2
WHERE gt.is_deleted = 0
  AND gt.status NOT IN (5, 6)
  AND gtu.users_id IS NULL
ORDER BY gt.date_creation ASC;
"""

# 3. Carga de Trabalho por Técnico (Volume de Chamados em Aberto por Pessoa)
SQL_WORKLOAD_PER_TECH = """
SELECT 
    UPPER(COALESCE(CONCAT(gu.firstname, ' ', gu.realname), gu.name, 'NÃO ATRIBUÍDO')) AS tecnico,
    COUNT(gt.id) AS total_pendentes,
    SUM(CASE WHEN DATEDIFF(CURDATE(), gt.date_creation) > 2 THEN 1 ELSE 0 END) AS em_atraso,
    MIN(gt.date_creation) AS chamado_mais_antigo
FROM glpi_tickets gt
LEFT JOIN glpi_tickets_users gtu ON gt.id = gtu.tickets_id AND gtu.type = 2
LEFT JOIN glpi_users gu ON gtu.users_id = gu.id
WHERE gt.is_deleted = 0
  AND gt.status NOT IN (5, 6)
GROUP BY tecnico
ORDER BY total_pendentes DESC;
"""

# 4. Chamados em Atraso Crítico (> SLA_WARNING_HOURS, ex: 48h)
SQL_OVERDUE_TICKETS = """
SELECT 
    gt.id AS id_chamado,
    UPPER(gt.name) AS titulo,
    UPPER(COALESCE(ge.name, 'NÃO INFORMADO')) AS unidade,
    UPPER(COALESCE(CONCAT(gu.firstname, ' ', gu.realname), gu.name, 'NÃO ATRIBUÍDO')) AS tecnico,
    gt.date_creation AS dt_abertura,
    TIMESTAMPDIFF(HOUR, gt.date_creation, NOW()) AS horas_aberto,
    UPPER(CASE gt.status
        WHEN 1 THEN 'Novo'
        WHEN 2 THEN 'Processando (Atribuído)'
        WHEN 3 THEN 'Processando (Planejado)'
        WHEN 4 THEN 'Pendente'
        ELSE 'Outro'
    END) AS status
FROM glpi_tickets gt
LEFT JOIN glpi_entities ge ON gt.entities_id = ge.id
LEFT JOIN glpi_tickets_users gtu ON gt.id = gtu.tickets_id AND gtu.type = 2
LEFT JOIN glpi_users gu ON gtu.users_id = gu.id
WHERE gt.is_deleted = 0
  AND gt.status NOT IN (5, 6)
  AND TIMESTAMPDIFF(HOUR, gt.date_creation, NOW()) >= %s
ORDER BY horas_aberto DESC
LIMIT 50;
"""

# 5. Chamados Sem Interação Recente (> INACTIVE_DAYS_THRESHOLD, ex: 7 dias)
SQL_INACTIVE_TICKETS = """
SELECT 
    gt.id AS id_chamado,
    UPPER(gt.name) AS titulo,
    UPPER(COALESCE(ge.name, 'NÃO INFORMADO')) AS unidade,
    UPPER(COALESCE(CONCAT(gu.firstname, ' ', gu.realname), gu.name, 'NÃO ATRIBUÍDO')) AS tecnico,
    gt.date_mod AS dt_ultima_mod,
    DATEDIFF(CURDATE(), gt.date_mod) AS dias_sem_interacao
FROM glpi_tickets gt
LEFT JOIN glpi_entities ge ON gt.entities_id = ge.id
LEFT JOIN glpi_tickets_users gtu ON gt.id = gtu.tickets_id AND gtu.type = 2
LEFT JOIN glpi_users gu ON gtu.users_id = gu.id
WHERE gt.is_deleted = 0
  AND gt.status NOT IN (5, 6)
  AND DATEDIFF(CURDATE(), gt.date_mod) >= %s
ORDER BY dias_sem_interacao DESC
LIMIT 50;
"""

# 6. Desempenho e Métricas por Unidade/Entidade
SQL_METRICS_BY_ENTITY = """
SELECT 
    UPPER(COALESCE(ge.name, 'NÃO INFORMADO')) AS unidade,
    COUNT(gt.id) AS total_geral,
    SUM(CASE WHEN gt.status NOT IN (5, 6) THEN 1 ELSE 0 END) AS abertos,
    SUM(CASE WHEN DATE(gt.solvedate) = CURDATE() THEN 1 ELSE 0 END) AS resolvidos_hoje,
    ROUND(AVG(CASE WHEN gt.solvedate IS NOT NULL AND DATE(gt.solvedate) = CURDATE() 
              THEN TIMESTAMPDIFF(SECOND, gt.date_creation, gt.solvedate)/3600 END), 1) AS mttr_horas
FROM glpi_tickets gt
LEFT JOIN glpi_entities ge ON gt.entities_id = ge.id
WHERE gt.is_deleted = 0
GROUP BY ge.name
ORDER BY abertos DESC
LIMIT 30;
"""

# ==============================================================================
# CONSULTAS PARA PERFORMANCE POR TÉCNICO, INSIGHTS E RANKING
# ==============================================================================

# 7. Performance por Técnico (Resolvidos Hoje + MTTR Corrido)
SQL_TECH_PERFORMANCE_TODAY = """
SELECT 
    UPPER(
        COALESCE(
            CONCAT(gu.firstname, ' ', gu.realname),
            gu.name,
            'NÃO ATRIBUÍDO'
        )
    ) AS tecnico,
    COUNT(DISTINCT gt.id) AS resolvidos_hoje,
    ROUND(
        AVG(TIMESTAMPDIFF(SECOND, gt.date_creation, gt.solvedate) / 3600),
        1
    ) AS mttr_corrido_horas
FROM glpi_tickets gt
LEFT JOIN glpi_tickets_users gtu 
    ON gt.id = gtu.tickets_id 
   AND gtu.type = 2
LEFT JOIN glpi_users gu 
    ON gtu.users_id = gu.id
WHERE gt.is_deleted = 0
  AND gt.solvedate IS NOT NULL
  AND DATE(gt.solvedate) = CURDATE()
  AND DATE(gt.solvedate) <= CURDATE()
GROUP BY tecnico
ORDER BY resolvidos_hoje DESC;
"""

# 8. Chamados com Solução Rejeitada (Detalhado)
SQL_REJECTED_SOLUTIONS_DETAIL = """
SELECT
    t.id AS chamado,
    t.name AS titulo,
    isol.date_creation AS data_solucao_proposta,
    isol.date_approval AS data_rejeicao,
    ge.name AS nome_unidade,
    UPPER(
        COALESCE(
            CONCAT(tec.firstname, ' ', tec.realname),
            tec.name,
            'NÃO ATRIBUÍDO'
        )
    ) AS tecnico_autor_solucao
FROM glpi_itilsolutions isol
INNER JOIN glpi_tickets t
    ON t.id = isol.items_id
   AND isol.itemtype = 'Ticket'
LEFT JOIN glpi_entities ge 
    ON ge.id = t.entities_id
LEFT JOIN glpi_users tec 
    ON tec.id = isol.users_id
WHERE isol.status = 4
  AND t.is_deleted = 0
  AND isol.date_approval IS NOT NULL
ORDER BY isol.date_approval DESC;
"""

# 9. Soluções Rejeitadas por Técnico (Agregado)
SQL_REJECTED_SOLUTIONS_PER_TECH = """
SELECT
    UPPER(
        COALESCE(
            CONCAT(tec.firstname, ' ', tec.realname),
            tec.name,
            'NÃO ATRIBUÍDO'
        )
    ) AS tecnico,
    COUNT(*) AS total_solucoes_recusadas
FROM glpi_itilsolutions isol
INNER JOIN glpi_tickets t 
    ON t.id = isol.items_id
   AND isol.itemtype = 'Ticket'
LEFT JOIN glpi_users tec 
    ON tec.id = isol.users_id
WHERE isol.status = 4
  AND t.is_deleted = 0
GROUP BY tecnico
ORDER BY total_solucoes_recusadas DESC;
"""

# 10. Tendência de Categorias (3 dias recentes vs 3 dias anteriores)
SQL_CATEGORY_TREND = """
SELECT 
    UPPER(COALESCE(gc.completename, gc.name, 'SEM CATEGORIA')) AS categoria,
    SUM(CASE 
        WHEN DATE(gt.date_creation) BETWEEN DATE_SUB(CURDATE(), INTERVAL 2 DAY) AND CURDATE()
        THEN 1 ELSE 0 END) AS qtd_recente,
    SUM(CASE 
        WHEN DATE(gt.date_creation) BETWEEN DATE_SUB(CURDATE(), INTERVAL 5 DAY) AND DATE_SUB(CURDATE(), INTERVAL 3 DAY)
        THEN 1 ELSE 0 END) AS qtd_anterior
FROM glpi_tickets gt
LEFT JOIN glpi_itilcategories gc 
    ON gt.itilcategories_id = gc.id
WHERE gt.is_deleted = 0
  AND DATE(gt.date_creation) >= DATE_SUB(CURDATE(), INTERVAL 5 DAY)
  AND DATE(gt.date_creation) <= CURDATE()
GROUP BY categoria
HAVING qtd_recente > 0 OR qtd_anterior > 0
ORDER BY qtd_recente DESC;
"""

# 11. Unidade Mais Impactada por Categoria com Tendência de Alta (CTE)
SQL_ENTITY_TREND = """
WITH tendencia AS (
    SELECT
        gt.itilcategories_id,
        SUM(CASE 
            WHEN DATE(gt.date_creation) BETWEEN DATE_SUB(CURDATE(), INTERVAL 2 DAY) AND CURDATE()
            THEN 1 ELSE 0 END) AS qtd_recente,
        SUM(CASE 
            WHEN DATE(gt.date_creation) BETWEEN DATE_SUB(CURDATE(), INTERVAL 5 DAY) AND DATE_SUB(CURDATE(), INTERVAL 3 DAY)
            THEN 1 ELSE 0 END) AS qtd_anterior
    FROM glpi_tickets gt
    WHERE gt.is_deleted = 0
      AND DATE(gt.date_creation) >= DATE_SUB(CURDATE(), INTERVAL 5 DAY)
      AND DATE(gt.date_creation) <= CURDATE()
    GROUP BY gt.itilcategories_id
    HAVING qtd_recente > qtd_anterior
),
por_unidade AS (
    SELECT
        gt.itilcategories_id,
        gt.entities_id,
        COUNT(*) AS total_recente,
        ROW_NUMBER() OVER (
            PARTITION BY gt.itilcategories_id
            ORDER BY COUNT(*) DESC
        ) AS rn
    FROM glpi_tickets gt
    WHERE gt.is_deleted = 0
      AND DATE(gt.date_creation) BETWEEN DATE_SUB(CURDATE(), INTERVAL 2 DAY) AND CURDATE()
    GROUP BY gt.itilcategories_id, gt.entities_id
)
SELECT
    UPPER(COALESCE(gc.completename, gc.name, 'SEM CATEGORIA')) AS categoria,
    UPPER(COALESCE(ge.name, 'NÃO INFORMADO')) AS unidade_mais_impactada,
    pu.total_recente,
    t.qtd_recente,
    t.qtd_anterior
FROM tendencia t
INNER JOIN por_unidade pu 
    ON pu.itilcategories_id = t.itilcategories_id
   AND pu.rn = 1
LEFT JOIN glpi_itilcategories gc 
    ON gc.id = t.itilcategories_id
LEFT JOIN glpi_entities ge 
    ON ge.id = pu.entities_id
ORDER BY t.qtd_recente DESC;
"""

# 12. Ranking Semanal de Técnicos (Resolvidos + MTTR)
SQL_RANKING_WEEKLY = """
SELECT 
    UPPER(
        COALESCE(
            CONCAT(gu.firstname, ' ', gu.realname),
            gu.name,
            'NÃO ATRIBUÍDO'
        )
    ) AS tecnico,
    COUNT(DISTINCT gt.id) AS resolvidos_semana,
    ROUND(
        AVG(TIMESTAMPDIFF(SECOND, gt.date_creation, gt.solvedate) / 3600),
        1
    ) AS mttr_corrido_horas
FROM glpi_tickets gt
LEFT JOIN glpi_tickets_users gtu 
    ON gt.id = gtu.tickets_id 
   AND gtu.type = 2
LEFT JOIN glpi_users gu 
    ON gtu.users_id = gu.id
WHERE gt.is_deleted = 0
  AND gt.solvedate IS NOT NULL
  AND YEARWEEK(gt.solvedate, 1) = YEARWEEK(CURDATE(), 1)
GROUP BY tecnico
ORDER BY resolvidos_semana DESC;
"""
