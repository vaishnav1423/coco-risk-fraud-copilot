# Project Instructions

## What this project is

A Risk, Fraud & AML compliance copilot for a bank, built for the Snowflake hackathon. It detects suspicious transaction patterns, lets compliance analysts investigate alerts with AI assistance, and produces auditable findings. All data is synthetic (Indian banking context, INR currency). No real customers or transactions are used anywhere.

## Folder structure

```
coco-risk-fraud-copilot/
├── syntheticData.py          # Primary data generator (Faker + pandas)
├── generate_data.py          # Older generator (superseded)
├── policy_docs.py            # 8 policies, 35 section-level chunks
├── streamlit_app.py          # Streamlit-in-Snowflake app (3 tabs)
├── sql/
│   ├── 01-setup.sql          # Role, warehouse, DB, tables, masking policy, Cortex Search
│   ├── 02-alerts.sql         # Detection CTEs, ALERTS table, ALERT_EVIDENCE view, RISK_FRAUD_SV
│   ├── 03-agent.sql          # RISK_EVIDENCE_SV semantic view, RISK_COPILOT agent
│   └── 04-findings.sql       # FINDINGS table (CREATE IF NOT EXISTS, never replace)
├── eval/
│   └── agent_eval_set.json   # 26 ground-truth questions for agent accuracy testing
├── docs/
│   └── architecture.md       # Mermaid architecture diagrams
├── data/                     # Generated CSVs (~50K transactions)
├── pyproject.toml
├── uv.lock
└── .python-version           # Python 3.11
```

## Snowflake objects

| Object | Name | Notes |
|--------|------|-------|
| Database | `RISK_FRAUD_DB` | |
| Schema | `RISK_FRAUD_DB.COPILOT` | All objects live here |
| Role | `RISK_COPILOT_ROLE` | Least-privilege role for non-admin work |
| Warehouse | `RISK_WH` | XS, auto-suspend 60s |
| Tables | `CUSTOMERS`, `ACCOUNTS`, `TRANSACTIONS`, `POLICY_DOCS`, `DETECTION_RULES`, `ALERTS`, `FINDINGS` | |
| View | `ALERT_EVIDENCE` | Joins alerts to their triggering transactions |
| Semantic views | `RISK_FRAUD_SV` (main, 5 tables), `RISK_EVIDENCE_SV` (evidence) | |
| Cortex Search | `POLICY_SEARCH` | Over POLICY_DOCS.text |
| Cortex Agent | `RISK_COPILOT` | 3 tools: RiskAnalyst, EvidenceAnalyst, PolicySearch |
| Masking policy | `CUSTOMER_NAME_MASK` | On CUSTOMERS.NAME; unmasks for ACCOUNTADMIN and RISK_COPILOT_ROLE |
| Streamlit app | `RISK_COPILOT_APP` | Warehouse runtime, staged at @STREAMLIT_STAGE |

## SQL execution order

Run the SQL files in Snowsight in this order. Each file depends on the one before it.

1. `sql/01-setup.sql` — creates role, warehouse, database, schema, tables, stage, loads CSVs, masking policy, Cortex Search
2. `sql/02-alerts.sql` — runs detection rules, creates ALERTS, ALERT_EVIDENCE, RISK_FRAUD_SV
3. `sql/03-agent.sql` — creates RISK_EVIDENCE_SV and RISK_COPILOT agent
4. `sql/04-findings.sql` — creates FINDINGS table (safe to re-run)

## Streamlit deployment

The app runs only inside Snowflake (Streamlit in Snowflake, warehouse runtime). There is no local `streamlit run` — the app uses `get_active_session()` and `_snowflake.send_snow_api_request` which exist only on the Snowflake warehouse runtime.

Deploy via SQL:

```sql
PUT 'file:///path/to/streamlit_app.py' @RISK_FRAUD_DB.COPILOT.STREAMLIT_STAGE
  AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

CREATE OR REPLACE STREAMLIT RISK_FRAUD_DB.COPILOT.RISK_COPILOT_APP
  ROOT_LOCATION = '@RISK_FRAUD_DB.COPILOT.STREAMLIT_STAGE'
  MAIN_FILE = 'streamlit_app.py'
  QUERY_WAREHOUSE = 'RISK_WH'
  TITLE = 'Risk & Compliance Copilot';
```

## Rules

### SQL safety

- Never run `DROP`, `TRUNCATE`, `REVOKE`, or `GRANT` without asking for confirmation first.
- Use `RISK_COPILOT_ROLE` for all non-admin work. Only switch to `ACCOUNTADMIN` when a privilege requires it, and switch back immediately after.
- Always `USE SCHEMA RISK_FRAUD_DB.COPILOT` before running queries.
- Use least-privilege grants. Never use `GRANT ALL`.
- Quote identifiers consistently. Use uppercase for Snowflake object names in SQL.

### Data integrity

- All data is synthetic. Never add real customer data to this project.
- Keep `injected_pattern` out of semantic views and anything the Cortex Agent can query. It is ground-truth labeling for evaluation only.
- The `FINDINGS` table uses `CREATE TABLE IF NOT EXISTS`, never `CREATE OR REPLACE`. Replacing it would wipe saved analyst findings.

### Compliance language

- Alerts are potential red flags, never proof of wrongdoing. Use words like "alert", "indicates", or "potential". Never state that fraud or a crime occurred.
- Findings stay in `DRAFT` status until a person reviews and signs off.
- Every answer and finding must cite policy section IDs (e.g. `POL-001-S3`) and transaction IDs (`txn_id`). Do not cite by document title alone.
