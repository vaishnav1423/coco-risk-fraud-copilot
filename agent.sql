-- =====================================================================
-- Step 3: Evidence semantic view + Cortex Agent
-- Run after 02_alerts_and_semantic_view.sql
-- =====================================================================
USE ROLE RISK_COPILOT_ROLE;
USE WAREHOUSE RISK_WH;
USE SCHEMA RISK_FRAUD_DB.COPILOT;

-- If CREATE AGENT fails with a privilege error, run once as ACCOUNTADMIN:
-- GRANT CREATE AGENT ON SCHEMA RISK_FRAUD_DB.COPILOT TO ROLE RISK_COPILOT_ROLE;

-- ---------------------------------------------------------------------
-- 1. Small semantic view over ALERT_EVIDENCE (transaction-level proof for each alert)
-- ---------------------------------------------------------------------
CREATE OR REPLACE SEMANTIC VIEW RISK_EVIDENCE_SV

  TABLES (
    evidence AS RISK_FRAUD_DB.COPILOT.ALERT_EVIDENCE
      PRIMARY KEY (alert_id, txn_id)
      WITH SYNONYMS ('supporting transactions', 'alert evidence')
      COMMENT = 'The exact transactions that triggered each alert. Amounts in INR'
  )

  DIMENSIONS (
    evidence.ev_alert_id AS alert_id
      COMMENT = 'Alert this transaction supports',
    evidence.ev_rule_id AS rule_id,
    evidence.ev_account_id AS account_id,
    evidence.ev_txn_id AS txn_id,
    evidence.ev_txn_ts AS txn_ts,
    evidence.ev_amount AS amount
      COMMENT = 'Transaction amount in INR',
    evidence.ev_channel AS channel,
    evidence.ev_counterparty_country AS counterparty_country
  )

  METRICS (
    evidence.ev_txn_count AS COUNT(evidence.txn_id)
      COMMENT = 'Number of supporting transactions',
    evidence.ev_total_amount AS SUM(evidence.amount)
      COMMENT = 'Total INR value of supporting transactions'
  )

  COMMENT = 'Transaction-level evidence behind alerts';

-- ---------------------------------------------------------------------
-- 2. The agent: Analyst (data) + Analyst (evidence) + Search (policies)
-- ---------------------------------------------------------------------
CREATE OR REPLACE AGENT RISK_COPILOT
  COMMENT = 'Risk, fraud and regulatory intelligence copilot'
  PROFILE = '{"display_name": "Risk & Compliance Copilot", "color": "blue"}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto
 
  orchestration:
    budget:
      seconds: 60
      tokens: 32000
 
  instructions:
    response: |
      You are a risk, fraud and AML copilot for compliance officers at a bank.
      Be concise and factual. All amounts are in INR.
      Rules for every answer:
      1. Ground every claim in tool results. Never invent numbers, IDs or policy text.
      2. Cite policy sections by ID (for example POL-001-S3) and transactions by txn_id.
      3. An alert is a potential red flag, not proof of wrongdoing. Use words like
         "alert", "indicates" or "potential"; never state that fraud or a crime occurred.
      4. If evidence or policy text is missing, say so and state what is missing.
      5. After EVERY statement taken from a policy, put its section ID in brackets,
         for example "(POL-001-S4)". Do not cite by document title alone.
      6. Do not offer to schedule reports or set up automations. Offer only to retrieve
         evidence, cite policy, or draft a finding for an alert.
      When asked for a finding or report on an alert, use this structure:
         Alert ID | Rule triggered | Entities (customer, account) | Supporting transactions |
         Policy clauses cited | Risk assessment | Recommended action and SLA.
    orchestration: |
      - Counts, totals, trends, customers, accounts and alerts: use RiskAnalyst.
      - The exact transactions behind a specific alert: use EvidenceAnalyst.
      - What a policy or regulation says, escalation steps, SLAs, required evidence,
        filing timelines: use PolicySearch.
      - For "what should we do about alert X" questions: first get the alert and its rule
        from RiskAnalyst, then use PolicySearch for that rule's policy section and its
        escalation and evidence sections, then EvidenceAnalyst for the transactions.
      - Retrieve several policy sections when the question is about required actions.
    sample_questions:
      - question: "How many high severity alerts are open, by alert type?"
      - question: "Which HIGH risk customers have structuring alerts?"
      - question: "What must we do when cash deposits are just below the reporting limit?"
      - question: "Show the transactions behind the largest high-risk jurisdiction alert and cite the policy."
 
  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "RiskAnalyst"
        description: "Answers questions about customers, accounts, transactions, alerts and detection rules using SQL over the governed risk semantic view. Use for counts, totals, rankings and filtering."
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "EvidenceAnalyst"
        description: "Returns the exact transactions that triggered a given alert (transaction IDs, timestamps, amounts, channel, counterparty country). Use to provide evidence for an alert."
    - tool_spec:
        type: "cortex_search"
        name: "PolicySearch"
        description: "Searches internal AML, fraud, KYC and liquidity policies and regulatory guidelines. Returns policy sections with IDs, for rules, thresholds, escalation workflow, SLAs, evidence requirements and reporting timelines."
 
  tool_resources:
    RiskAnalyst:
      semantic_view: "RISK_FRAUD_DB.COPILOT.RISK_FRAUD_SV"
      execution_environment:
        type: "warehouse"
        warehouse: "RISK_WH"
    EvidenceAnalyst:
      semantic_view: "RISK_FRAUD_DB.COPILOT.RISK_EVIDENCE_SV"
      execution_environment:
        type: "warehouse"
        warehouse: "RISK_WH"
    PolicySearch:
      search_service: "RISK_FRAUD_DB.COPILOT.POLICY_SEARCH"
      max_results: "6"
      title_column: "title"
      id_column: "section_id"
  $$;
 
SHOW AGENTS;
DESCRIBE AGENT RISK_COPILOT;
 
-- ---------------------------------------------------------------------
-- 3. Test it in Snowsight (easiest):
--    AI & ML > Agents > RISK_COPILOT > ask the sample questions.
--    If you don't see it, check the left menu for "Snowflake Intelligence" / "Agents".
-- ---------------------------------------------------------------------
 