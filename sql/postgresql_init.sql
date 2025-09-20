-- PostgreSQL initialization script for postfix-blocker
-- Everything under schema crisop
-- Emulates Db2 semantics (1024 OCTETS via octet_length checks; TIMESTAMP(6); IDENTITY ALWAYS)

-- 0) Schema
CREATE SCHEMA IF NOT EXISTS crisop;

-- 1) Table: crisop.blocked_addresses
CREATE TABLE IF NOT EXISTS crisop.blocked_addresses (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pattern    VARCHAR(255) NOT NULL,
    is_regex   BOOLEAN NOT NULL DEFAULT FALSE,
    test_mode  BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
);

-- 2) Table: crisop.cris_props
-- Emulate Db2 VARCHAR(1024 OCTETS) by enforcing a 1024-byte cap (not just characters).
CREATE TABLE IF NOT EXISTS crisop.cris_props (
    key       VARCHAR(1024) PRIMARY KEY,
    value     VARCHAR(1024),
    update_ts TIMESTAMP(6) WITHOUT TIME ZONE,
    CONSTRAINT cris_props_key_octets CHECK (octet_length(key)  <= 1024),
    CONSTRAINT cris_props_val_octets CHECK (value IS NULL OR octet_length(value) <= 1024),
    CONSTRAINT xpkcrisprops UNIQUE (key)    -- (optional) echoes the Db2 constraint name idea
);

-- 3) Trigger function to set updated_at on UPDATE for blocked_addresses
CREATE OR REPLACE FUNCTION crisop.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP(6);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4) Trigger (drop if exists, then create)
DROP TRIGGER IF EXISTS trg_blocked_addresses_set_updated_at ON crisop.blocked_addresses;

CREATE TRIGGER trg_blocked_addresses_set_updated_at
BEFORE UPDATE ON crisop.blocked_addresses
FOR EACH ROW
EXECUTE FUNCTION crisop.set_updated_at();
