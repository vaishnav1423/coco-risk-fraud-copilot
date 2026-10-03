-- =====================================================================
-- Step 2: Signals (ALERTS), Evidence (ALERT_EVIDENCE), Semantic View
-- Run after 01_setup.sql. Run section by section.
-- =====================================================================
USE ROLE RISK_COPILOT_ROLE;
USE WAREHOUSE RISK_WH;
USE SCHEMA RISK_FRAUD_DB.COPILOT;

-- If CREATE SEMANTIC VIEW fails with a privilege error, run once as ACCOUNTADMIN:
-- GRANT CREATE SEMANTIC VIEW ON SCHEMA RISK_FRAUD_DB.COPILOT TO ROLE RISK_COPILOT_ROLE;

-- ---------------------------------------------------------------------
-- 1. ALERTS: apply the policy rules (POL-001, POL-002, POL-003) to transactions
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE ALERTS AS
WITH
-- STR-R1: 3+ cash deposits of INR 9,00,000 - 9,99,999 within a rolling 7 days
cash AS (
  SELECT account_id, txn_ts, amount
  FROM TRANSACTIONS
  WHERE channel = 'CASH_DEPOSIT' AND amount BETWEEN 900000 AND 999999.99
),
str_win AS (
  SELECT c1.account_id,
         c1.txn_ts          AS window_start,
         MAX(c2.txn_ts)     AS window_end,
         COUNT(*)           AS txn_count,
         SUM(c2.amount)     AS total_amount
  FROM cash c1
  JOIN cash c2
    ON  c1.account_id = c2.account_id
    AND c2.txn_ts >= c1.txn_ts
    AND c2.txn_ts <  DATEADD('day', 7, c1.txn_ts)
  GROUP BY c1.account_id, c1.txn_ts
  HAVING COUNT(*) >= 3
),
str_alerts AS (
  SELECT 'STR-R1' AS rule_id, account_id, window_start, window_end, txn_count, total_amount,
         -- POL-001-S3: High if deposits fall within 48 hours
         IFF(DATEDIFF('hour', window_start, window_end) <= 48, 'HIGH', 'MEDIUM') AS severity
  FROM str_win
  QUALIFY ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY txn_count DESC, window_start) = 1
),
-- GEO-R1: single transfer above INR 20,00,000 to a listed jurisdiction (NG, KY)
geo_alerts AS (
  SELECT 'GEO-R1' AS rule_id, account_id, txn_ts AS window_start, txn_ts AS window_end,
         1 AS txn_count, amount AS total_amount, 'HIGH' AS severity
  FROM TRANSACTIONS
  WHERE amount > 2000000 AND counterparty_country IN ('NG', 'KY')
),
-- VEL-R1: more than 15 outgoing transfers within 60 minutes
-- (simplification: UPI / IMPS / NEFT treated as outgoing transfers)
xfers AS (
  SELECT account_id, txn_ts, amount
  FROM TRANSACTIONS
  WHERE channel IN ('UPI', 'IMPS', 'NEFT')
),
vel_win AS (
  SELECT x1.account_id,
         x1.txn_ts          AS window_start,
         MAX(x2.txn_ts)     AS window_end,
         COUNT(*)           AS txn_count,
         SUM(x2.amount)     AS total_amount
  FROM xfers x1
  JOIN xfers x2
    ON  x1.account_id = x2.account_id
    AND x2.txn_ts >= x1.txn_ts
    AND x2.txn_ts <  DATEADD('minute', 60, x1.txn_ts)
  GROUP BY x1.account_id, x1.txn_ts
  HAVING COUNT(*) > 15
),
vel_alerts AS (
  SELECT 'VEL-R1' AS rule_id, account_id, window_start, window_end, txn_count, total_amount,
         'MEDIUM' AS severity
  FROM vel_win
  QUALIFY ROW_NUMBER() OVER (
            PARTITION BY account_id, DATE(window_start)
            ORDER BY txn_count DESC, window_start) = 1
),
all_alerts AS (
  SELECT * FROM str_alerts
  UNION ALL SELECT * FROM geo_alerts
  UNION ALL SELECT * FROM vel_alerts
)
SELECT
  rule_id || '-' || account_id || '-' || TO_CHAR(window_start, 'YYYYMMDDHH24MISS') AS alert_id,
  rule_id, account_id, window_start, window_end, txn_count, total_amount, severity,
  'OPEN' AS status
FROM all_alerts;

SELECT rule_id, severity, COUNT(*) AS alerts FROM ALERTS GROUP BY 1, 2 ORDER BY 1, 2;

-- Quick check against the injected ground truth (accounts with each pattern):
SELECT injected_pattern, COUNT(DISTINCT account_id) AS accounts_with_pattern
FROM TRANSACTIONS WHERE injected_pattern IS NOT NULL GROUP BY 1;
-- Expect close matches. A few VELOCITY_BURST accounts may be missed on purpose:
-- bursts of exactly 15 transfers do not exceed the "more than 15" threshold in POL-003.

-- ---------------------------------------------------------------------
-- 2. ALERT_EVIDENCE: the exact transactions behind each alert
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW ALERT_EVIDENCE AS
SELECT a.alert_id, a.rule_id, a.account_id,
       t.txn_id, t.txn_ts, t.amount, t.channel, t.counterparty_country
FROM ALERTS a
JOIN TRANSACTIONS t
  ON  t.account_id = a.account_id
  AND t.txn_ts BETWEEN a.window_start AND a.window_end
WHERE (a.rule_id = 'STR-R1' AND t.channel = 'CASH_DEPOSIT' AND t.amount BETWEEN 900000 AND 999999.99)
   OR (a.rule_id = 'GEO-R1' AND t.amount > 2000000 AND t.counterparty_country IN ('NG', 'KY'))
   OR (a.rule_id = 'VEL-R1' AND t.channel IN ('UPI', 'IMPS', 'NEFT'));

-- Try it: evidence for one structuring alert
SELECT * FROM ALERT_EVIDENCE
WHERE alert_id = (SELECT MIN(alert_id) FROM ALERTS WHERE rule_id = 'STR-R1')
ORDER BY txn_ts;

-- ---------------------------------------------------------------------
-- 3. SEMANTIC VIEW (for Cortex Analyst). injected_pattern is NOT exposed.
-- ---------------------------------------------------------------------
CREATE OR REPLACE SEMANTIC VIEW RISK_FRAUD_SV

  TABLES (
    customers AS RISK_FRAUD_DB.COPILOT.CUSTOMERS
      PRIMARY KEY (customer_id)
      WITH SYNONYMS ('clients', 'account holders')
      COMMENT = 'Bank customers with KYC status and risk rating',
    accounts AS RISK_FRAUD_DB.COPILOT.ACCOUNTS
      PRIMARY KEY (account_id)
      COMMENT = 'Customer accounts (savings, current, loan). Amounts in INR',
    transactions AS RISK_FRAUD_DB.COPILOT.TRANSACTIONS
      PRIMARY KEY (txn_id)
      WITH SYNONYMS ('payments', 'transfers')
      COMMENT = 'Account transactions. Amounts in INR',
    alerts AS RISK_FRAUD_DB.COPILOT.ALERTS
      PRIMARY KEY (alert_id)
      WITH SYNONYMS ('flags', 'cases', 'suspicious activity')
      COMMENT = 'AML and fraud alerts raised by the detection rules',
    detection_rules AS RISK_FRAUD_DB.COPILOT.DETECTION_RULES
      PRIMARY KEY (rule_id)
      COMMENT = 'Detection rules, each linked to a policy section'
  )

  RELATIONSHIPS (
    accounts_to_customers AS accounts (customer_id) REFERENCES customers (customer_id),
    txns_to_accounts      AS transactions (account_id) REFERENCES accounts (account_id),
    alerts_to_accounts    AS alerts (account_id) REFERENCES accounts (account_id),
    alerts_to_rules       AS alerts (rule_id) REFERENCES detection_rules (rule_id)
  )

  DIMENSIONS (
    customers.customer_id AS customer_id,
    customers.customer_name AS name
      WITH SYNONYMS = ('customer', 'client name'),
    customers.customer_city AS city,
    customers.kyc_status AS kyc_status
      COMMENT = 'KYC verification status'
      SAMPLE_VALUES ('VERIFIED', 'PENDING', 'EXPIRED')
      IS_ENUM,
    customers.customer_risk_rating AS risk_rating
      COMMENT = 'Customer risk rating'
      SAMPLE_VALUES ('LOW', 'MEDIUM', 'HIGH')
      IS_ENUM,
    customers.customer_segment AS segment
      SAMPLE_VALUES ('RETAIL', 'SME', 'CORPORATE')
      IS_ENUM,

    accounts.account_id AS account_id,
    accounts.account_type AS account_type
      SAMPLE_VALUES ('SAVINGS', 'CURRENT', 'LOAN')
      IS_ENUM,

    transactions.txn_id AS txn_id,
    transactions.txn_ts AS txn_ts
      COMMENT = 'Transaction timestamp',
    transactions.txn_date AS DATE(txn_ts),
    transactions.txn_month AS DATE_TRUNC('month', txn_ts),
    transactions.channel AS channel
      COMMENT = 'Payment channel'
      SAMPLE_VALUES ('UPI', 'NEFT', 'RTGS', 'IMPS', 'CARD', 'ATM', 'CASH_DEPOSIT')
      IS_ENUM,
    transactions.counterparty_country AS counterparty_country
      COMMENT = 'ISO country code of the counterparty',
    transactions.merchant_category AS merchant_category,

    alerts.alert_id AS alert_id,
    alerts.alert_severity AS severity
      SAMPLE_VALUES ('HIGH', 'MEDIUM')
      IS_ENUM,
    alerts.alert_status AS status,
    alerts.alert_start AS window_start
      COMMENT = 'Start of the activity window that triggered the alert',
    alerts.alert_end AS window_end,
    alerts.alert_month AS DATE_TRUNC('month', window_start),

    detection_rules.rule_id AS rule_id
      SAMPLE_VALUES ('STR-R1', 'GEO-R1', 'VEL-R1')
      IS_ENUM,
    detection_rules.rule_name AS rule_name
      WITH SYNONYMS = ('alert type', 'pattern'),
    detection_rules.policy_section AS policy_section
      COMMENT = 'Policy section (POLICY_DOCS.section_id) that defines the rule'
  )

  METRICS (
    customers.customer_count AS COUNT(customers.customer_id)
      COMMENT = 'Number of customers',
    accounts.account_count AS COUNT(accounts.account_id)
      COMMENT = 'Number of accounts',
    accounts.total_balance AS SUM(accounts.balance)
      COMMENT = 'Total account balance in INR',
    transactions.txn_count AS COUNT(transactions.txn_id)
      COMMENT = 'Number of transactions',
    transactions.total_txn_amount AS SUM(transactions.amount)
      COMMENT = 'Total transaction value in INR',
    transactions.avg_txn_amount AS AVG(transactions.amount)
      COMMENT = 'Average transaction value in INR',
    alerts.alert_count AS COUNT(alerts.alert_id)
      COMMENT = 'Number of alerts',
    alerts.alerted_amount AS SUM(alerts.total_amount)
      COMMENT = 'Total INR value of activity behind alerts'
  )

  COMMENT = 'Risk, fraud and AML semantic view for the compliance copilot';

-- ---------------------------------------------------------------------
-- 4. Test queries (run each)
-- ---------------------------------------------------------------------
SHOW SEMANTIC VIEWS;
SHOW SEMANTIC METRICS IN RISK_FRAUD_SV;

-- Alerts by rule
SELECT * FROM SEMANTIC_VIEW(
  RISK_FRAUD_SV
  METRICS alerts.alert_count
  DIMENSIONS detection_rules.rule_name
);

-- Alerts by customer risk rating (traverses alerts -> accounts -> customers)
SELECT * FROM SEMANTIC_VIEW(
  RISK_FRAUD_SV
  METRICS alerts.alert_count
  DIMENSIONS customers.customer_risk_rating, alerts.alert_severity
);