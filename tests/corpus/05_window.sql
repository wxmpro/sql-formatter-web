-- 窗口函数: over 子句保持单行
SELECT
  ROW_NUMBER() OVER (PARTITION BY a.user_id ORDER BY a.create_time DESC) AS rn,
  SUM(a.amount) OVER (PARTITION BY a.user_id) AS user_amount,
  LAG(a.amount, 1) OVER (PARTITION BY a.user_id ORDER BY a.create_time) AS last_amount
FROM dw.t_order a
WHERE a.dt = '${bizdate}'
