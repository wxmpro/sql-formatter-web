-- DDL / DML 单行语句
TRUNCATE TABLE dw.t_order;
DELETE FROM dw.t_order WHERE dt = '2024-01-01';
CREATE TABLE IF NOT EXISTS dw.t_agg (
  id BIGINT,
  nm STRING,
  amt DECIMAL(18, 2),
  dt STRING
);
