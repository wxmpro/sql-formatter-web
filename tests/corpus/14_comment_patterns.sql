-- 注释形态全覆盖 (回归语料)
-- 独立行注释
SELECT
  a.id,
  ,b.name  -- 短字段备注: 同行
  ,c.amount -- 说明性字段备注, 内容较长需要独立成行以便阅读
  ,d.flag
FROM dw.t_order a
LEFT JOIN dw.t_user b ON a.uid = b.id
LEFT JOIN dw.t_pay c ON a.id = c.order_id
LEFT JOIN dw.t_dict d ON a.flag = d.code
WHERE a.dt = '${bizdate}'
-- 字符串里含 -- 不能被误判为注释边界
  AND a.note <> 'a -- b'
