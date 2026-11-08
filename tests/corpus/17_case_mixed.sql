-- CASE WHEN 与注释 / IN 列表 / 窗口函数组合 (回归语料)
SELECT
  CASE
    WHEN a.flg = 'A' THEN '签约'
    WHEN a.flg = 'B' THEN '筹备中'
    ELSE '未知'
  END AS status_desc,
  CASE
    WHEN a.c1 = 'X'
      AND a.c2 = 'Y'
      AND a.c3 = 'Z'
    THEN 1
    ELSE 0
  END AS is_valid,
  ROW_NUMBER() OVER (PARTITION BY a.id ORDER BY a.create_time DESC) AS rn,
  COUNT(*) AS cnt
FROM dw.t_order a
WHERE a.dt = '${bizdate}'
  AND a.flg IN ('A', 'B', 'C')
  AND a.typ IN ('X', 'Y', 'Z', 'W', 'V', 'U')
