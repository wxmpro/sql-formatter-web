-- 占位符 / 数字 / 标识符边界 (回归语料)
SELECT
  ods.seq_id.NEXTVAL AS id,
  'ods_rzt',
  'plateno_rzt_${tbl_name}',
  '${sch_time}',
  COUNT(*)
FROM ods_rzt.plateno_rzt_${tbl_name}
------------where  data_load_time='${sch_time}'
;

-- 1..col 是 Hive 语法: 数字 1 与两个点必须分开, 不能被吞成 1.
SELECT COUNT(*) FROM 1..db.tbl;

-- 引号标识符与关键字同形的列名
SELECT "SELECT" AS kw, "MyCol" AS c, `close` AS cl, count AS cnt FROM t;
