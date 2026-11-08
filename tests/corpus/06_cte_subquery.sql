-- CTE + 派生表 + 子查询
WITH t1 AS (
  SELECT a.id, a.name FROM dw.t_user a WHERE a.dt = '${bizdate}'
),
t2 AS (
  SELECT b.order_id, SUM(b.amount) AS amt FROM dw.t_order b GROUP BY b.order_id
)
SELECT
  t1.id,
  t1.name,
  (SELECT COUNT(*) FROM dw.t_log l WHERE l.order_id = t1.id) AS log_cnt,
  t2.amt
FROM t1
LEFT JOIN t2 ON t2.order_id = t1.id
