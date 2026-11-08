-- CASE WHEN 多分支短枚举: 每分支一行, 条件不展开 (D2)
SELECT
  CASE
    WHEN a.hotel_status = 'A' THEN '签约'
    WHEN a.hotel_status = 'B' THEN '筹备中'
    WHEN a.hotel_status = 'C' THEN '已终止'
    ELSE '未知'
  END AS hotel_status_desc,
  CASE
    WHEN a.flg = 'X' AND a.typ = 'Y' THEN 1
    WHEN a.flg = 'Z' AND a.typ = 'W' THEN 2
    ELSE 0
  END AS pair_flag
FROM dw.t_hotel a
