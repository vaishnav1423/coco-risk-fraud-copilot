-- =====================================================================
-- Risk, Fraud & Regulatory Copilot : Snowflake setup
-- Run in a Snowsight worksheet, section by section.
-- =====================================================================

-- ---------- 1. Role, warehouse, database, schema ----------
USE ROLE ACCOUNTADMIN;  -- if your hackathon account limits this, use SYSADMIN

CREATE ROLE IF NOT EXISTS RISK_COPILOT_ROLE;
GRANT ROLE RISK_COPILOT_ROLE TO ROLE SYSADMIN;
-- Also grant to your own user (replace YOUR_USER):
-- GRANT ROLE RISK_COPILOT_ROLE TO USER YOUR_USER;

CREATE WAREHOUSE IF NOT EXISTS RISK_WH
  WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;

CREATE DATABASE IF NOT EXISTS RISK_FRAUD_DB;
CREATE SCHEMA   IF NOT EXISTS RISK_FRAUD_DB.COPILOT;

GRANT USAGE ON WAREHOUSE RISK_WH TO ROLE RISK_COPILOT_ROLE;
GRANT ALL ON DATABASE RISK_FRAUD_DB TO ROLE RISK_COPILOT_ROLE;
GRANT ALL ON SCHEMA RISK_FRAUD_DB.COPILOT TO ROLE RISK_COPILOT_ROLE;
GRANT ALL ON FUTURE TABLES IN SCHEMA RISK_FRAUD_DB.COPILOT TO ROLE RISK_COPILOT_ROLE;

-- Cortex functions (usually already granted to PUBLIC; harmless to repeat)
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE RISK_COPILOT_ROLE;

USE ROLE RISK_COPILOT_ROLE;
USE WAREHOUSE RISK_WH;
USE SCHEMA RISK_FRAUD_DB.COPILOT;

-- ---------- 2. Tables (columns match the generated CSVs) ----------
CREATE OR REPLACE TABLE CUSTOMERS (
  customer_id   STRING,
  name          STRING,
  city          STRING,
  kyc_status    STRING,
  risk_rating   STRING,
  segment       STRING,
  onboarded_on  DATE
);

CREATE OR REPLACE TABLE ACCOUNTS (
  account_id           STRING,
  customer_id          STRING,
  account_type         STRING,
  balance              NUMBER(18,2),
  avg_monthly_inflow   NUMBER(18,2)
);

CREATE OR REPLACE TABLE TRANSACTIONS (
  txn_id               STRING,
  account_id           STRING,
  txn_ts               TIMESTAMP_NTZ,
  amount               NUMBER(18,2),
  channel              STRING,
  counterparty_country STRING,
  merchant_category    STRING,
  injected_pattern     STRING   -- ground-truth label: keep OUT of your semantic view
);

CREATE OR REPLACE TABLE POLICY_DOCS (
  doc_id         STRING,
  section_id     STRING,
  title          STRING,
  section_title  STRING,
  doc_type       STRING,
  category       STRING,
  version        STRING,
  effective_date DATE,
  owner          STRING,
  text           STRING
);

-- ---------- 3. Stage + file format ----------
CREATE OR REPLACE FILE FORMAT CSV_FMT
  TYPE = CSV
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  EMPTY_FIELD_AS_NULL = TRUE
  NULL_IF = ('', 'NaN');

CREATE OR REPLACE STAGE DATA_STAGE FILE_FORMAT = CSV_FMT;

-- Upload the 4 CSVs to the stage (pick ONE method):
--  A) Snowsight UI: Data > Databases > RISK_FRAUD_DB > COPILOT > Stages >
--     DATA_STAGE > "+ Files", then upload the CSVs from your local data\ folder.
--  B) Snowflake CLI / SnowSQL, e.g.:
--     PUT file://G:/CoCo/coco-risk-fraud-copilot/data/*.csv @DATA_STAGE AUTO_COMPRESS=TRUE;

LIST @DATA_STAGE;   -- confirm the 4 files are there

-- ---------- 4. Load ----------
COPY INTO CUSTOMERS    FROM @DATA_STAGE/customers.csv    ON_ERROR = 'ABORT_STATEMENT';
COPY INTO ACCOUNTS     FROM @DATA_STAGE/accounts.csv     ON_ERROR = 'ABORT_STATEMENT';
COPY INTO TRANSACTIONS FROM @DATA_STAGE/transactions.csv ON_ERROR = 'ABORT_STATEMENT';
COPY INTO POLICY_DOCS  FROM @DATA_STAGE/policy_docs.csv  ON_ERROR = 'ABORT_STATEMENT';
-- If you uploaded with AUTO_COMPRESS (PUT), the staged names end in .csv.gz:
-- adjust the paths above accordingly (check LIST output).

-- ---------- 5. Sanity checks ----------
SELECT 'CUSTOMERS' t, COUNT(*) n FROM CUSTOMERS
UNION ALL SELECT 'ACCOUNTS',     COUNT(*) FROM ACCOUNTS
UNION ALL SELECT 'TRANSACTIONS', COUNT(*) FROM TRANSACTIONS
UNION ALL SELECT 'POLICY_DOCS',  COUNT(*) FROM POLICY_DOCS;
-- Expected approx: 2000 / 2660 / 50736 / 35

SELECT injected_pattern, COUNT(*) FROM TRANSACTIONS GROUP BY 1;

-- ---------- 6. Detection rules table (links signals to policy clauses) ----------
CREATE OR REPLACE TABLE DETECTION_RULES (
  rule_id        STRING,
  rule_name      STRING,
  policy_section STRING,   -- joins to POLICY_DOCS.section_id
  severity       STRING,
  description    STRING
);

INSERT INTO DETECTION_RULES VALUES
 ('STR-R1','Cash structuring','POL-001-S3','HIGH',
  '3+ cash deposits of INR 9,00,000-9,99,999 within 7 days'),
 ('GEO-R1','High-risk jurisdiction transfer','POL-002-S3','HIGH',
  'Single transfer above INR 20,00,000 to a listed jurisdiction'),
 ('VEL-R1','Velocity burst','POL-003-S2','MEDIUM',
  'More than 15 outgoing transfers within 60 minutes');

-- ---------- 7. Cortex Search service on the policy text ----------
CREATE OR REPLACE CORTEX SEARCH SERVICE POLICY_SEARCH
  ON text
  ATTRIBUTES doc_id, section_id, title, section_title, doc_type, category, version
  WAREHOUSE = RISK_WH
  TARGET_LAG = '1 day'
  AS (
    SELECT text, doc_id, section_id, title, section_title,
           doc_type, category, version, effective_date, owner
    FROM POLICY_DOCS
  );

-- Test it
SELECT PARSE_JSON(
  SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'RISK_FRAUD_DB.COPILOT.POLICY_SEARCH',
    '{"query": "what must be done when cash deposits are just below the reporting limit?",
      "columns": ["section_id","title","text"],
      "limit": 3}'
  )
) AS result;