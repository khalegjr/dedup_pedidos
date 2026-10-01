BEGIN;

-- ==============================================================================
-- 1. CRIAÇÃO DAS TABELAS DE BACKUP (_bkp)
-- ==============================================================================
DROP TABLE IF EXISTS pedido_bkp CASCADE;
CREATE TABLE pedido_bkp AS
SELECT * FROM public.pedido;

DROP TABLE IF EXISTS item_pedido_bkp CASCADE;
CREATE TABLE item_pedido_bkp AS
SELECT * FROM public.item_pedido;

DROP TABLE IF EXISTS item_relacionado_bkp CASCADE;
CREATE TABLE item_relacionado_bkp AS
SELECT * FROM public.item_relacionado;


-- ==============================================================================
-- 2. CRIAÇÃO E POPULAÇÃO DA TABELA TEMPORÁRIA DE RELACIONAMENTOS (_tmp)
-- ==============================================================================
DROP TABLE IF EXISTS item_relacionado_tmp CASCADE;

CREATE TABLE item_relacionado_tmp AS
SELECT * FROM public.item_relacionado;

-- Adiciona os campos de apoio para o mapeamento dos novos IDs
ALTER TABLE item_relacionado_tmp
    ADD COLUMN numero_pedido VARCHAR(25),
    ADD COLUMN item_pedido INTEGER,
    ADD COLUMN filial VARCHAR(10),
    ADD COLUMN grupo_id VARCHAR(36),
    ADD COLUMN pedido_id_novo VARCHAR(36),
    ADD COLUMN item_pedido_id_novo VARCHAR(36);

-- Popula os metadados a partir das tabelas originais de pedido e item
UPDATE item_relacionado_tmp AS ir_tmp
SET
    numero_pedido = ped.numero_pedido,
    filial = ped.filial,
    grupo_id = ped.grupo_id
FROM public.pedido AS ped
WHERE ir_tmp.pedido_id = ped.id;

UPDATE item_relacionado_tmp AS ir_tmp
SET
    item_pedido = ip.item
FROM public.item_pedido AS ip
WHERE ir_tmp.item_pedido_id = ip.id;


-- ==============================================================================
-- 3. CRIAÇÃO DAS TABELAS DEDUPLICADAS (_tmp)
-- ==============================================================================
DROP TABLE IF EXISTS pedido_tmp CASCADE;
CREATE TABLE pedido_tmp AS
SELECT DISTINCT ON (ped.filial, ped.numero_pedido, ped.grupo_id) *
FROM public.pedido ped
ORDER BY ped.filial, ped.numero_pedido, ped.grupo_id, ped.id;

DROP TABLE IF EXISTS item_pedido_tmp CASCADE;
CREATE TABLE item_pedido_tmp AS
SELECT DISTINCT ON (ped.filial, ped.numero_pedido, ped.grupo_id, ip.item)
ip.*,
ped.filial AS ped_filial,
ped.numero_pedido AS ped_numero_pedido,
ped.grupo_id AS ped_grupo_id
FROM public.item_pedido ip
JOIN public.pedido ped ON ip.pedido_id = ped.id
ORDER BY ped.filial, ped.numero_pedido, ped.grupo_id, ip.item, ip.pedido_id, ip.id;

-- Corrige a FK pedido_id dentro de item_pedido_tmp apontando para os novos IDs de pedido_tmp
UPDATE item_pedido_tmp AS ipt
SET pedido_id = pt.id
FROM pedido_tmp AS pt
WHERE ipt.ped_filial = pt.filial
  AND ipt.ped_numero_pedido = pt.numero_pedido
  AND ipt.ped_grupo_id = pt.grupo_id;

-- Remove as colunas auxiliares de junção criadas em item_pedido_tmp
ALTER TABLE item_pedido_tmp
    DROP COLUMN ped_filial,
    DROP COLUMN ped_numero_pedido,
    DROP COLUMN ped_grupo_id;


-- ==============================================================================
-- 4. MAPEAMENTO DOS NOVOS IDS EM ITEM_RELACIONADO_TMP
-- ==============================================================================
-- Mapeia o novo ID do Pedido
UPDATE item_relacionado_tmp AS ir_tmp
SET pedido_id_novo = pt.id
FROM pedido_tmp AS pt
WHERE ir_tmp.filial = pt.filial
  AND ir_tmp.numero_pedido = pt.numero_pedido
  AND ir_tmp.grupo_id = pt.grupo_id;

-- Mapeia o novo ID do Item do Pedido
UPDATE item_relacionado_tmp AS ir_tmp
SET item_pedido_id_novo = ipt.id
FROM item_pedido_tmp AS ipt
JOIN pedido_tmp AS pt ON ipt.pedido_id = pt.id
WHERE ir_tmp.filial = pt.filial
  AND ir_tmp.numero_pedido = pt.numero_pedido
  AND ir_tmp.grupo_id = pt.grupo_id
  AND ir_tmp.item_pedido = ipt.item;


-- ==============================================================================
-- 5. ATUALIZAÇÃO DAS TABELAS ORIGINAIS (REORIENTAÇÃO DE FKS)
-- ==============================================================================
-- Atualiza as chaves da tabela item_relacionado original
UPDATE public.item_relacionado AS ir
SET
    pedido_id = t.pedido_id_novo,
    item_pedido_id = t.item_pedido_id_novo
FROM item_relacionado_tmp AS t
WHERE t.id = ir.id;


-- ==============================================================================
-- 6. LIMPEZA E DELEÇÃO DOS REGISTROS DUPLICADOS EXCEDENTES
-- ==============================================================================
-- Remove itens de pedido que foram descartados na deduplicação
DELETE FROM public.item_pedido
WHERE id NOT IN (SELECT id FROM item_pedido_tmp);

-- Remove cabeçalhos de pedido que foram descartados na deduplicação
DELETE FROM public.pedido
WHERE id NOT IN (SELECT id FROM pedido_tmp);


-- ==============================================================================
-- 7. RELATÓRIO DE CONFERÊNCIA E VERIFICAÇÃO DE DIFF
-- ==============================================================================
-- Tabela temporária para conferência antes x depois
DROP TABLE IF EXISTS relatorio_diff_tmp;

CREATE TEMP TABLE relatorio_diff_tmp AS
WITH resumo_antes AS (
    SELECT
        ir_bkp.filial,
        ir_bkp.numero_pedido,
        ir_bkp.grupo_id,
        ir_bkp.item_pedido AS item,
        COUNT(*) AS total_registros_antes,
        SUM(COALESCE(ir_bkp.quantidade_entrada, 0)) AS qtd_total_antes
    FROM item_relacionado_tmp ir_bkp
    GROUP BY ir_bkp.filial, ir_bkp.numero_pedido, ir_bkp.grupo_id, ir_bkp.item_pedido
),
resumo_depois AS (
    SELECT
        p.filial,
        p.numero_pedido,
        p.grupo_id,
        ip.item,
        COUNT(*) AS total_registros_depois,
        SUM(COALESCE(ir.quantidade_entrada, 0)) AS qtd_total_depois
    FROM public.item_relacionado ir
    JOIN public.pedido p ON ir.pedido_id = p.id
    JOIN public.item_pedido ip ON ir.item_pedido_id = ip.id
    GROUP BY p.filial, p.numero_pedido, p.grupo_id, ip.item
)
SELECT
    COALESCE(a.filial, d.filial) AS filial,
    COALESCE(a.numero_pedido, d.numero_pedido) AS numero_pedido,
    COALESCE(a.grupo_id, d.grupo_id) AS grupo_id,
    COALESCE(a.item, d.item) AS item,
    COALESCE(a.total_registros_antes, 0) AS registros_antes,
    COALESCE(d.total_registros_depois, 0) AS registros_depois,
    (COALESCE(d.total_registros_depois, 0) - COALESCE(a.total_registros_antes, 0)) AS diff_registros,
    COALESCE(a.qtd_total_antes, 0) AS qtd_antes,
    COALESCE(d.qtd_total_depois, 0) AS qtd_depois,
    (COALESCE(d.qtd_total_depois, 0) - COALESCE(a.qtd_total_antes, 0)) AS diff_quantidade
FROM resumo_antes a
FULL OUTER JOIN resumo_depois d
    ON a.filial = d.filial
   AND a.numero_pedido = d.numero_pedido
   AND a.grupo_id = d.grupo_id
   AND a.item = d.item;

-- Exibe o resultado do Relatório DIFF
SELECT * FROM relatorio_diff_tmp
ORDER BY filial, numero_pedido, grupo_id, item;

-- Limpeza das tabelas temporárias utilizadas no processo
DROP TABLE IF EXISTS pedido_tmp;
DROP TABLE IF EXISTS item_pedido_tmp;
DROP TABLE IF EXISTS item_relacionado_tmp;

-- Se o relatório acima mostrar diff_quantidade = 0 e diff_registros = 0, execute COMMIT.
-- Caso encontre divergências, execute ROLLBACK.
COMMIT;
--ROLLBACK;
