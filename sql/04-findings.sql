-- =====================================================================
-- Step 4: FINDINGS table (documented findings saved by the Streamlit app)
-- =====================================================================
USE ROLE RISK_COPILOT_ROLE;
USE WAREHOUSE RISK_WH;
USE SCHEMA RISK_FRAUD_DB.COPILOT;

CREATE TABLE IF NOT EXISTS FINDINGS (
  FINDING_ID         STRING        DEFAULT UUID_STRING(),
  ALERT_ID           STRING        REFERENCES ALERTS (alert_id),
  RULE_ID            STRING        REFERENCES DETECTION_RULES (rule_id),
  ACCOUNT_ID         STRING        REFERENCES ACCOUNTS (account_id),
  CUSTOMER_ID        STRING        REFERENCES CUSTOMERS (customer_id),
  SEVERITY           STRING,
  DISPOSITION        STRING,       -- per POL-005-S1
  FINDING_TEXT       STRING,       -- the documented finding (cites policy section IDs)
  ANALYST_NOTES      STRING,
  RISK_ASSESSMENT    STRING,
  RECOMMENDED_ACTION STRING,
  POLICY_SECTIONS    STRING,       -- e.g. 'POL-001-S3, POL-001-S4'
  EVIDENCE_TXN_IDS   STRING,
  STATUS             STRING        DEFAULT 'DRAFT',  -- DRAFT until reviewer sign-off
  CREATED_BY         STRING        DEFAULT CURRENT_USER(),
  CREATED_AT         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

DESC TABLE FINDINGS;
SELECT COUNT(*) AS findings FROM FINDINGS;