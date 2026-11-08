-- 注释: 行内注释 / 独占注释行
SELECT
  a.id,
  -- 订单金额
  a.amount,
  a.flg -- 状态标记
FROM dw.t_order a
WHERE a.dt = '${bizdate}'
  -- 仅看有效订单
  AND a.flg = 'A'
