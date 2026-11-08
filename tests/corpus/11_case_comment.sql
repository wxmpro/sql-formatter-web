-- CASE WHEN 内含行内注释: 必须强制拆行, 防注释吞掉 then/end
SELECT
  CASE
    WHEN a.flg = 'A' -- 状态 A
    THEN 1
    WHEN a.flg = 'B'
    THEN 2
    ELSE 0
  END AS flg_flag
FROM dw.t_order a
