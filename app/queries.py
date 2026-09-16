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
