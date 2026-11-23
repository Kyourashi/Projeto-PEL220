-- ================================================================================================
--  PEL220 - Questão de pesquisa da Aula 8: quanto custa o esquema do Cygnus
--  ("uma linha por atributo, tudo em texto"), em espaço e em tempo de consulta?
--
--  Copia o histórico real do nó da estufa para um banco de teste (pesquisa_tmp) até ter 1 e
--  7 dias de dados, mede o espaço por linha e cronometra a mesma consulta do painel (janela de
--  30 min) nas duas tabelas. No fim, apaga o banco de teste. Precisa de algum histórico da estufa.
--
--      docker exec -i db-mysql mysql -uroot -p123 -t < ferramentas/custo_cygnus.sql
--
--  Leva cerca de 30 s e usa ≈ 500 MB de disco enquanto roda.
-- ================================================================================================

SHOW CREATE TABLE estufa.`urn_ngsi-ld_Device_ESP32-001_Device`;        -- nove colunas TEXT, sem índice

DROP DATABASE IF EXISTS pesquisa_tmp;
CREATE DATABASE pesquisa_tmp;

-- o histórico real, numerado por atributo na ordem em que chegou
CREATE TABLE pesquisa_tmp.base AS
  SELECT attrName, ROW_NUMBER() OVER (PARTITION BY attrName ORDER BY CAST(recvTimeTs AS UNSIGNED)) AS i,
         recvTime, fiwareServicePath, entityId, entityType, attrType, attrValue, attrMd
  FROM estufa.`urn_ngsi-ld_Device_ESP32-001_Device`;
ALTER TABLE pesquisa_tmp.base ADD INDEX (attrName(32), i);
CREATE TABLE pesquisa_tmp.contagem AS SELECT attrName, COUNT(*) AS n FROM pesquisa_tmp.base GROUP BY attrName;

-- 0, 1, 2 ... 120.959: as medidas de 5 s de 7 dias
SET SESSION cte_max_recursion_depth = 1000000;
CREATE TABLE pesquisa_tmp.seq (k INT PRIMARY KEY);
INSERT INTO pesquisa_tmp.seq
  WITH RECURSIVE s(k) AS (SELECT 0 UNION ALL SELECT k + 1 FROM s WHERE k < 120959) SELECT k FROM s;

-- cada atributo ganha uma linha a cada 5 s, terminando agora; os valores e os metadados se repetem
-- em ciclo a partir do histórico real, então o tamanho das linhas é o de verdade
CREATE TABLE pesquisa_tmp.d1 LIKE estufa.`urn_ngsi-ld_Device_ESP32-001_Device`;
SET @T := (UNIX_TIMESTAMP() - 86400) * 1000;
INSERT INTO pesquisa_tmp.d1
  SELECT CAST(@T + s.k * 5000 AS CHAR), b.recvTime, b.fiwareServicePath, b.entityId, b.entityType,
         b.attrName, b.attrType, b.attrValue, b.attrMd
  FROM pesquisa_tmp.seq s JOIN pesquisa_tmp.contagem c
  JOIN pesquisa_tmp.base b ON b.attrName = c.attrName AND b.i = (s.k MOD c.n) + 1
  WHERE s.k < 17280;

CREATE TABLE pesquisa_tmp.d7 LIKE estufa.`urn_ngsi-ld_Device_ESP32-001_Device`;
SET @T := (UNIX_TIMESTAMP() - 7 * 86400) * 1000;
INSERT INTO pesquisa_tmp.d7
  SELECT CAST(@T + s.k * 5000 AS CHAR), b.recvTime, b.fiwareServicePath, b.entityId, b.entityType,
         b.attrName, b.attrType, b.attrValue, b.attrMd
  FROM pesquisa_tmp.seq s JOIN pesquisa_tmp.contagem c
  JOIN pesquisa_tmp.base b ON b.attrName = c.attrName AND b.i = (s.k MOD c.n) + 1;
ANALYZE TABLE pesquisa_tmp.d1, pesquisa_tmp.d7;

-- espaço: bytes por linha no disco (dados do InnoDB ÷ linhas)
SELECT t.table_name AS tabela, c.linhas, ROUND(c.horas, 1) AS horas, t.data_length AS bytes,
       ROUND(t.data_length / c.linhas) AS bytes_por_linha, t.index_length AS bytes_de_indice
FROM information_schema.tables t
JOIN (SELECT 'd1' AS nome, COUNT(*) AS linhas,
             (MAX(CAST(recvTimeTs AS UNSIGNED)) - MIN(CAST(recvTimeTs AS UNSIGNED))) / 3600000 AS horas
      FROM pesquisa_tmp.d1
      UNION ALL
      SELECT 'd7', COUNT(*), (MAX(CAST(recvTimeTs AS UNSIGNED)) - MIN(CAST(recvTimeTs AS UNSIGNED))) / 3600000
      FROM pesquisa_tmp.d7) c ON c.nome = t.table_name
WHERE t.table_schema = 'pesquisa_tmp';
SELECT @@innodb_buffer_pool_size / 1048576 AS cache_do_innodb_mb;

-- tempo: a consulta da série de temperatura do painel, janela de 30 min (≈ 360 linhas)
-- 1 vez para aquecer o cache e 3 medidas em cada tabela; veja a coluna Duration (s) no fim
SET profiling = 1;
SET profiling_history_size = 20;
SELECT COUNT(*) AS d1_aquecimento FROM (SELECT recvTimeTs / 1000 AS t, CAST(attrValue AS DECIMAL(6,1)) AS v
  FROM pesquisa_tmp.d1 WHERE attrName = 'temperature'
  AND recvTimeTs / 1000 BETWEEN UNIX_TIMESTAMP() - 1800 AND UNIX_TIMESTAMP() ORDER BY recvTimeTs) x;
SELECT COUNT(*) AS d1 FROM (SELECT recvTimeTs / 1000 AS t, CAST(attrValue AS DECIMAL(6,1)) AS v
  FROM pesquisa_tmp.d1 WHERE attrName = 'temperature'
  AND recvTimeTs / 1000 BETWEEN UNIX_TIMESTAMP() - 1800 AND UNIX_TIMESTAMP() ORDER BY recvTimeTs) x;
SELECT COUNT(*) AS d1 FROM (SELECT recvTimeTs / 1000 AS t, CAST(attrValue AS DECIMAL(6,1)) AS v
  FROM pesquisa_tmp.d1 WHERE attrName = 'temperature'
  AND recvTimeTs / 1000 BETWEEN UNIX_TIMESTAMP() - 1800 AND UNIX_TIMESTAMP() ORDER BY recvTimeTs) x;
SELECT COUNT(*) AS d1 FROM (SELECT recvTimeTs / 1000 AS t, CAST(attrValue AS DECIMAL(6,1)) AS v
  FROM pesquisa_tmp.d1 WHERE attrName = 'temperature'
  AND recvTimeTs / 1000 BETWEEN UNIX_TIMESTAMP() - 1800 AND UNIX_TIMESTAMP() ORDER BY recvTimeTs) x;
SELECT COUNT(*) AS d7_aquecimento FROM (SELECT recvTimeTs / 1000 AS t, CAST(attrValue AS DECIMAL(6,1)) AS v
  FROM pesquisa_tmp.d7 WHERE attrName = 'temperature'
  AND recvTimeTs / 1000 BETWEEN UNIX_TIMESTAMP() - 1800 AND UNIX_TIMESTAMP() ORDER BY recvTimeTs) x;
SELECT COUNT(*) AS d7 FROM (SELECT recvTimeTs / 1000 AS t, CAST(attrValue AS DECIMAL(6,1)) AS v
  FROM pesquisa_tmp.d7 WHERE attrName = 'temperature'
  AND recvTimeTs / 1000 BETWEEN UNIX_TIMESTAMP() - 1800 AND UNIX_TIMESTAMP() ORDER BY recvTimeTs) x;
SELECT COUNT(*) AS d7 FROM (SELECT recvTimeTs / 1000 AS t, CAST(attrValue AS DECIMAL(6,1)) AS v
  FROM pesquisa_tmp.d7 WHERE attrName = 'temperature'
  AND recvTimeTs / 1000 BETWEEN UNIX_TIMESTAMP() - 1800 AND UNIX_TIMESTAMP() ORDER BY recvTimeTs) x;
SELECT COUNT(*) AS d7 FROM (SELECT recvTimeTs / 1000 AS t, CAST(attrValue AS DECIMAL(6,1)) AS v
  FROM pesquisa_tmp.d7 WHERE attrName = 'temperature'
  AND recvTimeTs / 1000 BETWEEN UNIX_TIMESTAMP() - 1800 AND UNIX_TIMESTAMP() ORDER BY recvTimeTs) x;
SHOW PROFILES;

-- por que não melhora com a janela menor: sem índice, o plano lê a tabela inteira (type = ALL)
EXPLAIN SELECT recvTimeTs FROM pesquisa_tmp.d7
WHERE attrName = 'temperature' AND recvTimeTs / 1000 > UNIX_TIMESTAMP() - 1800;

DROP DATABASE pesquisa_tmp;
