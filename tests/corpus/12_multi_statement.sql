-- 多语句 + PL/SQL 风格块 + SET
SET hive.exec.dynamic.partition = true;

SELECT a.id FROM dw.t_order a;

DECLARE v_cnt INT;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM dw.t_order;
END;
