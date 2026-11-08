-- 基础 SELECT: 字段列表 / 逗号顶格 / as 别名对齐
SELECT
  a.id,
  a.name,
  NVL(b.amount, 0) AS amount,
  c.create_time AS ctime
FROM dw.t_order a
LEFT JOIN dw.t_user b ON a.user_id = b.id
LEFT JOIN dw.t_dim c ON a.dim_id = c.id
WHERE a.dt = '${bizdate}'
  AND a.status = 'A'
