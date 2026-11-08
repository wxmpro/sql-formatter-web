-- CASE WHEN 单分支: 应整块一行 (D1)
SELECT
  CASE WHEN a.flg = 'A' THEN '是' ELSE '否' END AS flg_desc,
  CASE WHEN a.c1 = 'X' AND a.c2 = 'Y' THEN 1 ELSE 0 END AS is_valid,
  CASE WHEN a.c1 = 'X' AND a.c2 = 'Y' AND a.c3 = 'Z' THEN 1 ELSE 0 END AS is_valid3
FROM dw.t_order a
