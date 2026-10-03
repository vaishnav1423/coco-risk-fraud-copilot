-- =====================================================================
-- Step 4: FINDINGS table (documented findings saved by the Streamlit app)
-- Safe to run whether or not you already created a FINDINGS table:
-- it creates the table if missing, then adds any columns the app needs.
-- =====================================================================
USE ROLE RISK_COPILOT_ROLE;
USE WAREHOUSE RISK_WH;
USE SCHEMA RISK_FRAUD_DB.COPILOT;

CREATE TABLE IF NOT EXISTS FINDINGS (
  FINDING_ID         STRING        DEFAULT UUID_STRING(),
  ALERT_ID           STRING,
  RULE_ID            STRING,
  DISPOSITION        STRING,       -- per POL-005-S1
  FINDING_TEXT       STRING,       -- the documented finding (cites policy section IDs)
  ANALYST_NOTES      STRING,
  CREATED_BY         STRING        DEFAULT CURRENT_USER(),
  CREATED_AT         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Extra columns used by the app (no-ops if they already exist)
ALTER TABLE FINDINGS ADD COLUMN IF NOT EXISTS ACCOUNT_ID         STRING;
ALTER TABLE FINDINGS ADD COLUMN IF NOT EXISTS CUSTOMER_ID        STRING;
ALTER TABLE FINDINGS ADD COLUMN IF NOT EXISTS SEVERITY           STRING;
ALTER TABLE FINDINGS ADD COLUMN IF NOT EXISTS RISK_ASSESSMENT    STRING;
ALTER TABLE FINDINGS ADD COLUMN IF NOT EXISTS RECOMMENDED_ACTION STRING;
ALTER TABLE FINDINGS ADD COLUMN IF NOT EXISTS POLICY_SECTIONS    STRING;  -- 'POL-001-S3, POL-001-S4'
ALTER TABLE FINDINGS ADD COLUMN IF NOT EXISTS EVIDENCE_TXN_IDS   STRING;
ALTER TABLE FINDINGS ADD COLUMN IF NOT EXISTS STATUS             STRING;  -- DRAFT until reviewer sign-off

DESC TABLE FINDINGS;
SELECT COUNT(*) AS findings FROM FINDINGS;