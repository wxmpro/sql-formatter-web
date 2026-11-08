-- PL/SQL 块: BEGIN...END 的 end 不能被当成 CASE 的 end (回归语料)
BEGIN
  DECLARE v_cnt INT;
  SELECT COUNT(*) INTO v_cnt FROM dw.t_order WHERE dt = '${bizdate}';
  IF v_cnt > 0 THEN
    INSERT INTO dw.t_log SELECT 'ok', v_cnt;
  END IF;
  COMMIT;
END;
