"""
Enriched SYNTHETIC policy / regulatory documents, one row per section (chunk).
Thresholds match the injected patterns in generate_data.py.
NOTE: Internal policy text is fictional. Regulatory references are illustrative;
verify against official sources before presenting them as real citations.
"""
import pandas as pd

DOCS = [
    {
        "doc_id": "POL-001", "title": "AML Structuring Policy", "doc_type": "POLICY",
        "version": "3.2", "effective_date": "2026-01-01", "owner": "Head of AML Compliance",
        "category": "AML",
        "sections": [
            ("Purpose and Scope",
             "This policy defines how the bank detects and escalates structuring, the practice of splitting "
             "cash transactions into smaller amounts to avoid reporting thresholds. It applies to all savings, "
             "current and loan accounts across retail, SME and corporate segments."),
            ("Definitions",
             "Structuring means three or more cash deposits by the same account within a rolling 7-day window, "
             "each between INR 9,00,000 and INR 9,99,999, where the combined value exceeds INR 10,00,000. "
             "The reporting threshold refers to the INR 10,00,000 cash transaction reporting limit."),
            ("Detection Rules",
             "Rule STR-R1: three or more CASH_DEPOSIT transactions of INR 9,00,000 to 9,99,999 in 7 days. "
             "Rule STR-R2: the same pattern across multiple accounts of one customer, aggregated at customer level. "
             "Alerts are scored High when the deposits fall within 48 hours, and Medium otherwise."),
            ("Escalation Workflow",
             "Level 1 analyst reviews within 1 business day. Confirmed or unresolved alerts go to the AML "
             "Compliance Officer within 2 business days. The Principal Officer decides on filing a Suspicious "
             "Transaction Report (STR), which must be filed within 7 working days of concluding suspicion."),
            ("Evidence Required",
             "The case file must contain the transaction list with IDs and timestamps, the account and customer "
             "profile, KYC status, average monthly inflow compared with deposited amounts, and the analyst's "
             "written rationale. Conclusions without transaction-level evidence are not accepted for closure."),
            ("Confidentiality",
             "Staff must not inform the customer that an alert or STR exists (no tipping-off). Case notes are "
             "restricted to the AML team and Internal Audit."),
            ("Record Retention",
             "Alerts, case files and STR copies are retained for at least 5 years from case closure."),
        ],
    },
    {
        "doc_id": "POL-002", "title": "High-Risk Jurisdiction Transfers", "doc_type": "POLICY",
        "version": "2.4", "effective_date": "2026-01-01", "owner": "Head of Financial Crime Compliance",
        "category": "AML",
        "sections": [
            ("Purpose and Scope",
             "This policy governs outgoing and incoming transfers involving counterparties in jurisdictions the "
             "bank classifies as high risk. It covers RTGS, NEFT, IMPS and card cross-border flows."),
            ("High-Risk Jurisdiction List",
             "For this synthetic bank, the internal high-risk list includes Nigeria (NG) and the Cayman Islands "
             "(KY). The list is reviewed quarterly by the Financial Crime Committee."),
            ("Detection Rules",
             "Rule GEO-R1: any single transfer above INR 20,00,000 to a counterparty in a listed jurisdiction "
             "is held for review. Rule GEO-R2: cumulative transfers above INR 50,00,000 to listed jurisdictions "
             "within 30 days from one customer also trigger review."),
            ("Required Controls",
             "Enhanced Due Diligence (EDD) is mandatory before release: purpose of payment, relationship to "
             "counterparty, source of funds and supporting documents such as invoices or contracts. Release "
             "needs written approval from a Compliance Officer."),
            ("Escalation and SLA",
             "Held transfers must be reviewed within 1 business day. If documents are not supplied within "
             "5 business days, the transfer is rejected and the case is evaluated for STR filing."),
            ("Exceptions",
             "Pre-approved corporate clients with a documented trade-finance relationship may use a "
             "streamlined review, but the transfer must still be logged with its justification."),
        ],
    },
    {
        "doc_id": "POL-003", "title": "Velocity Monitoring Rule", "doc_type": "POLICY",
        "version": "1.8", "effective_date": "2026-01-01", "owner": "Head of Fraud Risk",
        "category": "FRAUD",
        "sections": [
            ("Purpose and Scope",
             "This rule detects account takeover, mule activity and automated fraud by monitoring the speed "
             "of outgoing payments. It applies to UPI, IMPS and NEFT channels."),
            ("Detection Rules",
             "Rule VEL-R1: more than 15 outgoing transfers within 60 minutes from one account triggers an "
             "automatic temporary hold. Rule VEL-R2: more than 10 transfers of INR 2,000 to INR 9,999 within "
             "30 minutes to different beneficiaries is flagged as a possible mule or scam pattern."),
            ("Automated Response",
             "The system places a temporary hold on further outgoing payments and sends an alert to the "
             "customer's registered mobile number. The hold lasts up to 24 hours unless released earlier "
             "by a fraud analyst."),
            ("Analyst Review",
             "The fraud analyst checks device and location changes, new beneficiaries, recent credential "
             "changes and the customer's normal activity. Outcomes are: release, confirm fraud and block, "
             "or escalate to AML if funds appear to be layered through mule accounts."),
            ("Customer Communication",
             "Customers are contacted through verified channels only. Staff must never ask for PINs, OTPs "
             "or passwords."),
        ],
    },
    {
        "doc_id": "REG-001", "title": "KYC Periodic Review Guideline", "doc_type": "REGULATION",
        "version": "2.0", "effective_date": "2025-04-01", "owner": "Head of KYC Operations",
        "category": "KYC",
        "sections": [
            ("Review Frequency",
             "KYC refresh is required every 2 years for high-risk customers, every 8 years for medium-risk "
             "customers and every 10 years for low-risk customers, counted from the last verification."),
            ("Restrictions on Expired KYC",
             "Accounts with expired KYC must be restricted after notice to the customer. Restricted accounts "
             "may receive credits but outgoing debits are blocked until KYC is refreshed."),
            ("Risk Rating Linkage",
             "Customers rated HIGH, and customers with open AML alerts, are prioritised for early refresh. "
             "A pending KYC status combined with high-value transactions must be reported to compliance."),
        ],
    },
    {
        "doc_id": "POL-004", "title": "Enhanced Due Diligence Procedure", "doc_type": "POLICY",
        "version": "1.5", "effective_date": "2026-01-01", "owner": "Head of KYC Operations",
        "category": "KYC",
        "sections": [
            ("When EDD Applies",
             "EDD applies to HIGH risk-rated customers, transactions with high-risk jurisdictions, customers "
             "with adverse media, and accounts whose activity departs sharply from their expected profile."),
            ("EDD Steps",
             "Verify source of funds and source of wealth, confirm beneficial ownership for non-individual "
             "customers, obtain senior management approval, and increase monitoring frequency to monthly."),
            ("Documentation",
             "EDD records must show who performed the review, what documents were checked, the outcome and "
             "the next review date."),
        ],
    },
    {
        "doc_id": "POL-005", "title": "Alert Disposition and Case Documentation", "doc_type": "POLICY",
        "version": "2.1", "effective_date": "2026-01-01", "owner": "Head of Compliance Operations",
        "category": "GOVERNANCE",
        "sections": [
            ("Disposition Categories",
             "Every alert must be closed as one of: False Positive, Suspicious (escalated), Confirmed Fraud, "
             "or Insufficient Information (pending). Each closure needs a written rationale."),
            ("Finding Report Format",
             "A documented finding contains: alert ID, rule triggered, entities involved, supporting "
             "transactions, policy clauses cited, risk assessment, recommended action, and reviewer sign-off."),
            ("Audit Trail",
             "All queries, evidence and decisions are time-stamped and attributable to a named user. Audit-ready "
             "reports must be reproducible from stored evidence."),
            ("Quality Review",
             "A 10 percent sample of closed alerts is re-reviewed monthly by Compliance QA. Closure without "
             "evidence is recorded as a control failure."),
        ],
    },
    {
        "doc_id": "POL-006", "title": "STR Filing Procedure", "doc_type": "POLICY",
        "version": "1.9", "effective_date": "2026-01-01", "owner": "Principal Officer",
        "category": "AML",
        "sections": [
            ("Filing Timeline",
             "An STR must be filed with the Financial Intelligence Unit within 7 working days of the Principal "
             "Officer concluding that the activity is suspicious. Attempted transactions are also reportable."),
            ("STR Contents",
             "Include customer identifiers, account numbers, transaction details, red flags observed, the "
             "grounds for suspicion and supporting documents. Narrative must be factual and specific."),
            ("Post-Filing",
             "Continue monitoring the account, apply additional controls if required, and review whether the "
             "customer relationship should continue. No tipping-off."),
        ],
    },
    {
        "doc_id": "REG-002", "title": "Record Retention and Reporting Requirements", "doc_type": "REGULATION",
        "version": "1.2", "effective_date": "2025-04-01", "owner": "Chief Compliance Officer",
        "category": "GOVERNANCE",
        "sections": [
            ("Retention Periods",
             "Transaction records and customer identification records are retained for at least 5 years after "
             "the transaction or the end of the business relationship, whichever is later."),
            ("Cash Transaction Reporting",
             "Cash transactions above INR 10,00,000, and integrally connected series of cash transactions "
             "within a month, are reported to the FIU by the 15th of the following month."),
        ],
    },
    {
        "doc_id": "POL-007", "title": "Liquidity Risk Monitoring (LCR)", "doc_type": "POLICY",
        "version": "1.3", "effective_date": "2026-01-01", "owner": "Head of Treasury Risk",
        "category": "LIQUIDITY",
        "sections": [
            ("Liquidity Coverage Ratio Floor",
             "The bank maintains a Liquidity Coverage Ratio of at least 100 percent, computed as high-quality "
             "liquid assets divided by net cash outflows over 30 days. An internal early-warning trigger "
             "is set at 110 percent."),
            ("Escalation",
             "A breach of the early-warning trigger is reported to the ALCO within 1 business day. A breach "
             "below 100 percent requires an immediate remediation plan and regulatory notification."),
        ],
    },
]


def build_policy_docs() -> pd.DataFrame:
    rows = []
    for d in DOCS:
        for n, (sec_title, text) in enumerate(d["sections"], start=1):
            rows.append({
                "doc_id": d["doc_id"],
                "section_id": f"{d['doc_id']}-S{n}",
                "title": d["title"],
                "section_title": sec_title,
                "doc_type": d["doc_type"],
                "category": d["category"],
                "version": d["version"],
                "effective_date": d["effective_date"],
                "owner": d["owner"],
                # Index this column in Cortex Search; context helps retrieval
                "text": f"{d['title']} ({d['doc_id']}) - {sec_title}: {text}",
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build_policy_docs()
    print(df.groupby("doc_id").size())