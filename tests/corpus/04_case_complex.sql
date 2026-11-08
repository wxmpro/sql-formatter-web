-- CASE WHEN 复杂条件: 条件展开, then 回到 when 缩进 (D3)
SELECT
  CASE
    WHEN a.c1 = 'X'
      AND a.c2 = 'Y'
      AND a.c3 = 'Z'
    THEN 1
    WHEN a.c1 = 'P' OR a.c2 = 'Q'
    THEN 2
    ELSE 0
  END AS complex_flag
FROM dw.t_order a
