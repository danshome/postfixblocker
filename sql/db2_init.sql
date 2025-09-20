-- =========================
-- Db2 LUW init (create-or-drop+recreate if different)
-- Everything under schema CRISOP
-- =========================

------------------------------------------------------------
-- 0) Parameters
------------------------------------------------------------
-- Require a 32K bufferpool named BP32K and a 32K tablespace named TS32K.
-- You can tweak the bufferpool SIZE if you like.
------------------------------------------------------------

------------------------------------------------------------
-- 1) BUFFERPOOL BP32K (32K)
--  - Create if missing
--  - If exists with wrong pagesize, drop & recreate
--  - If size is smaller than desired, grow it (safe)
------------------------------------------------------------
BEGIN
  DECLARE v_bp_exists   INT DEFAULT 0;
  DECLARE v_pg          INT DEFAULT 0;

  SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0)
    INTO v_bp_exists, v_pg
    FROM SYSCAT.BUFFERPOOLS
   WHERE BPNAME='BP32K';

  IF v_bp_exists = 0 THEN
    EXECUTE IMMEDIATE 'CREATE BUFFERPOOL BP32K SIZE 1000 PAGESIZE 32K';
  ELSE
    IF v_pg <> 32768 THEN
      -- Wrong pagesize; must drop & recreate
      EXECUTE IMMEDIATE 'DROP BUFFERPOOL BP32K';
      EXECUTE IMMEDIATE 'CREATE BUFFERPOOL BP32K SIZE 1000 PAGESIZE 32K';
    ELSE
      -- (Optional) ensure minimum size
      BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION BEGIN END;
        EXECUTE IMMEDIATE 'ALTER BUFFERPOOL BP32K SIZE 1000';
      END;
    END IF;
  END IF;
END;

------------------------------------------------------------
-- 2) TABLESPACE TS32K (32K, automatic storage, BP32K)
--  - Create if missing
--  - If exists but pagesize != 32K, drop & recreate
--  - If exists with 32K, try to ensure BP is BP32K
------------------------------------------------------------
BEGIN
  DECLARE v_ts_exists INT DEFAULT 0;
  DECLARE v_pg        INT DEFAULT 0;

  SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0)
    INTO v_ts_exists, v_pg
    FROM SYSCAT.TABLESPACES
   WHERE TBSPACE='TS32K';

  IF v_ts_exists = 0 THEN
    EXECUTE IMMEDIATE
      'CREATE TABLESPACE TS32K '||
      '  PAGESIZE 32K '||
      '  MANAGED BY AUTOMATIC STORAGE '||
      '  EXTENTSIZE 32 '||
      '  BUFFERPOOL BP32K';
  ELSE
    IF v_pg <> 32768 THEN
      EXECUTE IMMEDIATE 'DROP TABLESPACE TS32K';
      EXECUTE IMMEDIATE
        'CREATE TABLESPACE TS32K '||
        '  PAGESIZE 32K '||
        '  MANAGED BY AUTOMATIC STORAGE '||
        '  EXTENTSIZE 32 '||
        '  BUFFERPOOL BP32K';
    ELSE
      -- Keep TS; try to point it at BP32K (ignore if already set)
      BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION BEGIN END;
        EXECUTE IMMEDIATE 'ALTER TABLESPACE TS32K BUFFERPOOL BP32K';
      END;
    END IF;
  END IF;
END;

------------------------------------------------------------
-- 3) SCHEMA CRISOP
--  - Create if missing (schema has no shape to compare)
------------------------------------------------------------
BEGIN
  DECLARE CONTINUE HANDLER FOR SQLSTATE '42710' BEGIN END;
  EXECUTE IMMEDIATE 'CREATE SCHEMA CRISOP';
END;

------------------------------------------------------------
-- 4) TABLE CRISOP.BLOCKED_ADDRESSES
--  - If missing: create in TS32K
--  - If exists: validate essential shape; if different, drop & recreate
------------------------------------------------------------
BEGIN
  DECLARE v_exists INT DEFAULT 0;

  SELECT COUNT(*) INTO v_exists
    FROM SYSCAT.TABLES
   WHERE TABSCHEMA='CRISOP' AND TABNAME='BLOCKED_ADDRESSES';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE
      'CREATE TABLE CRISOP.BLOCKED_ADDRESSES ( '||
      '  ID         INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 1, INCREMENT BY 1) PRIMARY KEY, '||
      '  PATTERN    VARCHAR(255) NOT NULL, '||
      '  IS_REGEX   SMALLINT NOT NULL DEFAULT 0, '||
      '  TEST_MODE  SMALLINT NOT NULL DEFAULT 1, '||
      '  UPDATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP '||
      ') IN TS32K INDEX IN TS32K';
  ELSE
    -- Check column count
    IF (SELECT COUNT(*) FROM SYSCAT.COLUMNS
         WHERE TABSCHEMA='CRISOP' AND TABNAME='BLOCKED_ADDRESSES') <> 5
    THEN
      EXECUTE IMMEDIATE 'DROP TABLE CRISOP.BLOCKED_ADDRESSES';
      EXECUTE IMMEDIATE
        'CREATE TABLE CRISOP.BLOCKED_ADDRESSES ( '||
        '  ID         INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 1, INCREMENT BY 1) PRIMARY KEY, '||
        '  PATTERN    VARCHAR(255) NOT NULL, '||
        '  IS_REGEX   SMALLINT NOT NULL DEFAULT 0, '||
        '  TEST_MODE  SMALLINT NOT NULL DEFAULT 1, '||
        '  UPDATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP '||
        ') IN TS32K INDEX IN TS32K';
    ELSE
      -- Spot-check each column + PK; if any mismatch => drop & recreate
      IF NOT EXISTS (SELECT 1 FROM SYSCAT.COLUMNS
                      WHERE TABSCHEMA='CRISOP' AND TABNAME='BLOCKED_ADDRESSES'
                        AND COLNAME='ID' AND TYPENAME='INTEGER' AND NULLS='N')
      OR NOT EXISTS (SELECT 1 FROM SYSCAT.COLUMNS
                      WHERE TABSCHEMA='CRISOP' AND TABNAME='BLOCKED_ADDRESSES'
                        AND COLNAME='PATTERN' AND TYPENAME='VARCHAR' AND LENGTH=255 AND NULLS='N')
      OR NOT EXISTS (SELECT 1 FROM SYSCAT.COLUMNS
                      WHERE TABSCHEMA='CRISOP' AND TABNAME='BLOCKED_ADDRESSES'
                        AND COLNAME='IS_REGEX' AND TYPENAME='SMALLINT' AND NULLS='N')
      OR NOT EXISTS (SELECT 1 FROM SYSCAT.COLUMNS
                      WHERE TABSCHEMA='CRISOP' AND TABNAME='BLOCKED_ADDRESSES'
                        AND COLNAME='TEST_MODE' AND TYPENAME='SMALLINT' AND NULLS='N')
      OR NOT EXISTS (SELECT 1 FROM SYSCAT.COLUMNS
                      WHERE TABSCHEMA='CRISOP' AND TABNAME='BLOCKED_ADDRESSES'
                        AND COLNAME='UPDATED_AT' AND TYPENAME='TIMESTAMP' AND NULLS='N')
      OR NOT EXISTS (
            SELECT 1
              FROM SYSCAT.TABCONST tc
              JOIN SYSCAT.KEYCOLUSE k
                ON k.CONSTNAME=tc.CONSTNAME AND k.TABSCHEMA=tc.TABSCHEMA
             WHERE tc.TABSCHEMA='CRISOP' AND tc.TABNAME='BLOCKED_ADDRESSES' AND tc.TYPE='P'
             GROUP BY tc.CONSTNAME
            HAVING COUNT(*)=1 AND MIN(k.COLNAME)='ID' AND MAX(k.COLNAME)='ID'
          )
      THEN
        EXECUTE IMMEDIATE 'DROP TABLE CRISOP.BLOCKED_ADDRESSES';
        EXECUTE IMMEDIATE
          'CREATE TABLE CRISOP.BLOCKED_ADDRESSES ( '||
          '  ID         INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 1, INCREMENT BY 1) PRIMARY KEY, '||
          '  PATTERN    VARCHAR(255) NOT NULL, '||
          '  IS_REGEX   SMALLINT NOT NULL DEFAULT 0, '||
          '  TEST_MODE  SMALLINT NOT NULL DEFAULT 1, '||
          '  UPDATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP '||
          ') IN TS32K INDEX IN TS32K';
      END IF;
    END IF;
  END IF;
END;

------------------------------------------------------------
-- 5) TABLE CRISOP.CRIS_PROPS
--  - If missing: create in TS32K
--  - If exists: validate essential shape; if different, drop & recreate
------------------------------------------------------------
BEGIN
  DECLARE v_exists INT DEFAULT 0;

  SELECT COUNT(*) INTO v_exists
    FROM SYSCAT.TABLES
   WHERE TABSCHEMA='CRISOP' AND TABNAME='CRIS_PROPS';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE
      'CREATE TABLE CRISOP.CRIS_PROPS ( '||
      '  KEY        VARCHAR(1024 OCTETS) NOT NULL, '||
      '  VALUE      VARCHAR(1024 OCTETS), '||
      '  UPDATE_TS  TIMESTAMP(6), '||
      '  CONSTRAINT XPKCRISPROPS PRIMARY KEY (KEY) '||
      ') IN TS32K INDEX IN TS32K';
  ELSE
    -- Check column count
    IF (SELECT COUNT(*) FROM SYSCAT.COLUMNS
         WHERE TABSCHEMA='CRISOP' AND TABNAME='CRIS_PROPS') <> 3
    THEN
      EXECUTE IMMEDIATE 'DROP TABLE CRISOP.CRIS_PROPS';
      EXECUTE IMMEDIATE
        'CREATE TABLE CRISOP.CRIS_PROPS ( '||
        '  KEY        VARCHAR(1024 OCTETS) NOT NULL, '||
        '  VALUE      VARCHAR(1024 OCTETS), '||
        '  UPDATE_TS  TIMESTAMP(6), '||
        '  CONSTRAINT XPKCRISPROPS PRIMARY KEY (KEY) '||
        ') IN TS32K INDEX IN TS32K';
    ELSE
      -- Spot-check columns + PK; if any mismatch => drop & recreate
      IF NOT EXISTS (SELECT 1 FROM SYSCAT.COLUMNS
                      WHERE TABSCHEMA='CRISOP' AND TABNAME='CRIS_PROPS'
                        AND COLNAME='KEY' AND TYPENAME='VARCHAR' AND LENGTH=1024 AND NULLS='N')
      OR NOT EXISTS (SELECT 1 FROM SYSCAT.COLUMNS
                      WHERE TABSCHEMA='CRISOP' AND TABNAME='CRIS_PROPS'
                        AND COLNAME='VALUE' AND TYPENAME='VARCHAR' AND LENGTH=1024 AND NULLS='Y')
      OR NOT EXISTS (SELECT 1 FROM SYSCAT.COLUMNS
                      WHERE TABSCHEMA='CRISOP' AND TABNAME='CRIS_PROPS'
                        AND COLNAME='UPDATE_TS' AND TYPENAME='TIMESTAMP' AND SCALE=6)
      OR NOT EXISTS (
            SELECT 1
              FROM SYSCAT.TABCONST tc
              JOIN SYSCAT.KEYCOLUSE k
                ON k.CONSTNAME=tc.CONSTNAME AND k.TABSCHEMA=tc.TABSCHEMA
             WHERE tc.TABSCHEMA='CRISOP' AND tc.TABNAME='CRIS_PROPS' AND tc.TYPE='P'
             GROUP BY tc.CONSTNAME
            HAVING COUNT(*)=1 AND MIN(k.COLNAME)='KEY' AND MAX(k.COLNAME)='KEY'
          )
      THEN
        EXECUTE IMMEDIATE 'DROP TABLE CRISOP.CRIS_PROPS';
        EXECUTE IMMEDIATE
          'CREATE TABLE CRISOP.CRIS_PROPS ( '||
          '  KEY        VARCHAR(1024 OCTETS) NOT NULL, '||
          '  VALUE      VARCHAR(1024 OCTETS), '||
          '  UPDATE_TS  TIMESTAMP(6), '||
          '  CONSTRAINT XPKCRISPROPS PRIMARY KEY (KEY) '||
          ') IN TS32K INDEX IN TS32K';
      END IF;
    END IF;
  END IF;
END;

------------------------------------------------------------
-- 6) TRIGGER (always refresh safely)
--  - CREATE OR REPLACE does not drop the table/data
------------------------------------------------------------
CREATE OR REPLACE TRIGGER CRISOP.TRG_BLOCKED_ADDRESSES_SET_UPDATED
NO CASCADE BEFORE UPDATE ON CRISOP.BLOCKED_ADDRESSES
REFERENCING NEW AS N
FOR EACH ROW
SET N.UPDATED_AT = CURRENT TIMESTAMP;
