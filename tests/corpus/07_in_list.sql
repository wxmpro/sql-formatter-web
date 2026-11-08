-- IN 列表 / 多值集合
SELECT a.id
FROM dw.t_order a
WHERE a.status IN ('A', 'B', 'C')
  AND a.typ IN ('X', 'Y', 'Z', 'W', 'V', 'U')
  AND a.flg NOT IN ('D')
