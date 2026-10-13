"""
Risk & Compliance Copilot - Streamlit in Snowflake (warehouse runtime)
Tabs: Alert queue | Case view + finding | Ask the copilot (Cortex Agent)
All data is synthetic.
"""
import json

import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session

DB, SCHEMA, AGENT = "RISK_FRAUD_DB", "COPILOT", "RISK_COPILOT"
T = f"{DB}.{SCHEMA}"

st.set_page_config(page_title="Risk & Compliance Copilot", layout="wide")
session = get_active_session()

# --- pure helpers start -------------------------------------------------
# Policy sections that govern each detection rule (see policy_docs.py)
RULE_POLICY = {
    "STR-R1": ["POL-001-S3", "POL-001-S4", "POL-001-S5", "POL-006-S1"],
    "GEO-R1": ["POL-002-S3", "POL-002-S4", "POL-002-S5"],
    "VEL-R1": ["POL-003-S2", "POL-003-S3", "POL-003-S4"],
}
RECOMMENDED = {
    "STR-R1": ("Level 1 analyst review within 1 business day (POL-001-S4). Escalate to the AML "
               "Compliance Officer within 2 business days. The Principal Officer decides on STR "
               "filing, due within 7 working days of concluding suspicion (POL-001-S4, POL-006-S1). "
               "Do not inform the customer (POL-001-S6)."),
    "GEO-R1": ("Hold the transfer. Complete Enhanced Due Diligence and obtain written Compliance "
               "Officer approval before release (POL-002-S4). Review within 1 business day; if "
               "documents are not supplied within 5 business days, reject and evaluate for STR "
               "(POL-002-S5)."),
    "VEL-R1": ("Keep the temporary hold (up to 24 hours) and have a fraud analyst review device "
               "and location changes, new beneficiaries and credential changes (POL-003-S3, "
               "POL-003-S4). Escalate to AML if mule layering is suspected."),
}


DISPOSITIONS = ["Suspicious (escalated)", "False Positive", "Confirmed Fraud",
                "Insufficient Information (pending)"]  # POL-005-S1


def esc(v):
    """Escape a value for a single-quoted Snowflake string literal."""
    return str(v).replace("\\", "\\\\").replace("'", "''")


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return extract_text(content.get("content", content.get("text", "")))
    if isinstance(content, list):
        return "".join(i.get("text", "") for i in content
                       if isinstance(i, dict) and i.get("type") == "text")
    return ""


def parse_agent_response(raw):
    """Handle either a plain JSON reply or a server-sent-events stream."""
    try:
        obj = json.loads(raw)
        return extract_text(obj.get("content", obj) if isinstance(obj, dict) else obj)
    except (json.JSONDecodeError, TypeError):
        pass
    final, deltas, event = None, [], None
    for line in str(raw).splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].strip()
            if data == "[DONE]":
                continue
            try:
                d = json.loads(data)
            except json.JSONDecodeError:
                continue
            if event == "response":
                final = extract_text(d.get("content", [])) if isinstance(d, dict) else None
            elif event and event.endswith("text.delta") and isinstance(d, dict) and d.get("text"):
                deltas.append(d["text"])
    return final or "".join(deltas)


def build_finding(row, ev_ids, policy_rows, disposition="", notes=""):
    """Deterministic, explainable finding. No opaque scoring."""
    factors = [f"Rule {row['RULE_ID']} ({row['RULE_NAME']}) fired with {row['SEVERITY']} severity."]
    factors.append(f"Customer risk rating is {row['RISK_RATING']}.")
    extra_sections = []
    if row["KYC_STATUS"] == "EXPIRED":
        factors.append("KYC is EXPIRED; accounts with expired KYC must be restricted (REG-001-S2).")
        extra_sections.append("REG-001-S2")
    elif row["KYC_STATUS"] == "PENDING":
        factors.append("KYC is PENDING with high-value activity; report to compliance (REG-001-S3).")
        extra_sections.append("REG-001-S3")
    inflow = float(row["AVG_MONTHLY_INFLOW"] or 0)
    total = float(row["TOTAL_AMOUNT"])
    if inflow > 0 and total / inflow >= 1:
        factors.append(f"Alerted value is {total / inflow:.1f}x the account's average monthly inflow.")
    risk = "\n".join(f"- {f}" for f in factors)
    action = RECOMMENDED[row["RULE_ID"]]
    ids = RULE_POLICY[row["RULE_ID"]] + extra_sections
    shown = ", ".join(ev_ids[:15]) + (f" ... (+{len(ev_ids) - 15} more)" if len(ev_ids) > 15 else "")
    clauses = "\n".join(
        f"- **{p['SECTION_ID']}** ({p['TITLE']} - {p['SECTION_TITLE']}): "
        f"{p['TEXT'].split(': ', 1)[-1]}" for p in policy_rows)
    report = f"""# Finding: alert {row['ALERT_ID']}
*Status: DRAFT - requires reviewer sign-off. This is a potential red flag, not a confirmed finding.*

**Rule triggered:** {row['RULE_ID']} - {row['RULE_NAME']}
**Entities:** customer {row['CUSTOMER_ID']} ({row['CUSTOMER_NAME']}), account {row['ACCOUNT_ID']}
**Activity window:** {row['WINDOW_START']} to {row['WINDOW_END']}
**Supporting transactions:** {len(ev_ids)} totalling INR {total:,.2f}
Transaction IDs: {shown}
**Disposition (POL-005-S1):** {disposition}

## Policy clauses cited
{clauses}

## Risk assessment
{risk}

## Recommended action
{action}

## Analyst notes
{notes or '(none)'}

**Reviewer sign-off:** ______________________   **Date:** ____________
"""
    return {"risk": risk, "action": action, "sections": ids, "report": report}
# --- pure helpers end ---------------------------------------------------


@st.cache_data(ttl=30)
def load_alerts():
    df = session.sql(f"""
        SELECT a.ALERT_ID, a.RULE_ID, r.RULE_NAME, a.SEVERITY, a.STATUS,
               a.WINDOW_START, a.WINDOW_END, a.TXN_COUNT, a.TOTAL_AMOUNT, a.ACCOUNT_ID,
               c.CUSTOMER_ID, c.NAME AS CUSTOMER_NAME, c.RISK_RATING, c.KYC_STATUS,
               ac.AVG_MONTHLY_INFLOW, f.FINDING_ID
        FROM {T}.ALERTS a
        JOIN {T}.DETECTION_RULES r ON r.RULE_ID = a.RULE_ID
        JOIN {T}.ACCOUNTS ac ON ac.ACCOUNT_ID = a.ACCOUNT_ID
        JOIN {T}.CUSTOMERS c ON c.CUSTOMER_ID = ac.CUSTOMER_ID
        LEFT JOIN (SELECT ALERT_ID, MAX(FINDING_ID) AS FINDING_ID
                   FROM {T}.FINDINGS GROUP BY 1) f ON f.ALERT_ID = a.ALERT_ID
        ORDER BY a.TOTAL_AMOUNT DESC""").to_pandas()
    df["TOTAL_AMOUNT"] = df["TOTAL_AMOUNT"].astype(float)
    df["AVG_MONTHLY_INFLOW"] = df["AVG_MONTHLY_INFLOW"].astype(float)
    return df


def call_agent(history):
    import _snowflake  # available on the warehouse runtime
    path = f"/api/v2/databases/{DB}/schemas/{SCHEMA}/agents/{AGENT}:run"
    body = {"messages": [{"role": m["role"],
                          "content": [{"type": "text", "text": m["content"]}]} for m in history]}
    return _snowflake.send_snow_api_request("POST", path, {}, {}, body, None, 120000)


# ------------------------------- sidebar --------------------------------
who = session.sql("SELECT CURRENT_USER() U, CURRENT_ROLE() R").collect()[0]
st.sidebar.title("Risk & Compliance Copilot")
st.sidebar.caption(f"Running as {who['U']} / role {who['R']}")
st.sidebar.caption("Synthetic data only. Alerts are potential red flags, not proof.")
st.sidebar.subheader("Try asking")
for q in ["How many high severity alerts are open, by alert type?",
          "Which HIGH risk customers have structuring alerts?",
          "What must we do when cash deposits are just below the reporting limit?",
          "Show the transactions behind the largest high-risk jurisdiction alert and cite the policy."]:
    if st.sidebar.button(q, key=q):
        st.session_state["queued"] = q

alerts = load_alerts()
tab1, tab2, tab3 = st.tabs(["Alert queue", "Case view & finding", "Ask the copilot"])

# ------------------------------ alert queue ------------------------------
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Alerts", len(alerts))
    c2.metric("High severity", int((alerts["SEVERITY"] == "HIGH").sum()))
    c3.metric("With a finding", int(alerts["FINDING_ID"].notna().sum()))
    c4.metric("Alerted value (INR)", f"{alerts['TOTAL_AMOUNT'].sum():,.0f}")
    f1, f2 = st.columns(2)
    sev = f1.multiselect("Severity", sorted(alerts["SEVERITY"].unique()),
                         default=sorted(alerts["SEVERITY"].unique()))
    rules = f2.multiselect("Rule", sorted(alerts["RULE_NAME"].unique()),
                           default=sorted(alerts["RULE_NAME"].unique()))
    view = alerts[alerts["SEVERITY"].isin(sev) & alerts["RULE_NAME"].isin(rules)].copy()
    view["HAS_FINDING"] = view["FINDING_ID"].notna()
    st.dataframe(view[["ALERT_ID", "RULE_NAME", "SEVERITY", "CUSTOMER_NAME", "RISK_RATING",
                       "KYC_STATUS", "TXN_COUNT", "TOTAL_AMOUNT", "HAS_FINDING"]].reset_index(drop=True),
                 use_container_width=True)
    st.bar_chart(view.groupby("RULE_NAME")["ALERT_ID"].count())

# --------------------------- case view & finding -------------------------
with tab2:
    ids = alerts["ALERT_ID"].tolist()
    labels = {r.ALERT_ID: f"{r.RULE_ID} | {r.CUSTOMER_NAME} | INR {r.TOTAL_AMOUNT:,.0f} | {r.ALERT_ID}"
              for r in alerts.itertuples()}
    pick = st.selectbox("Select an alert", ids, format_func=lambda i: labels[i])
    row = alerts[alerts["ALERT_ID"] == pick].iloc[0]

    a, b, c = st.columns(3)
    a.metric("Rule", f"{row['RULE_ID']}")
    b.metric("Severity", row["SEVERITY"])
    c.metric("Alerted value (INR)", f"{row['TOTAL_AMOUNT']:,.0f}")
    st.write(f"**Customer:** {row['CUSTOMER_NAME']} ({row['CUSTOMER_ID']}) | risk rating "
             f"{row['RISK_RATING']} | KYC {row['KYC_STATUS']} | account {row['ACCOUNT_ID']}")

    st.subheader("Evidence: supporting transactions")
    ev = session.sql(f"""SELECT TXN_ID, TXN_TS, AMOUNT, CHANNEL, COUNTERPARTY_COUNTRY
                         FROM {T}.ALERT_EVIDENCE WHERE ALERT_ID = '{esc(pick)}'
                         ORDER BY TXN_TS""").to_pandas()
    st.dataframe(ev.reset_index(drop=True), use_container_width=True)

    sections = RULE_POLICY[row["RULE_ID"]]
    plist = ", ".join(f"'{s}'" for s in sections)
    pol = session.sql(f"""SELECT SECTION_ID, TITLE, SECTION_TITLE, TEXT FROM {T}.POLICY_DOCS
                          WHERE SECTION_ID IN ({plist}) ORDER BY SECTION_ID""").to_pandas()
    st.subheader("Policy basis")
    for p in pol.itertuples():
        with st.expander(f"{p.SECTION_ID} - {p.TITLE}: {p.SECTION_TITLE}"):
            st.write(p.TEXT.split(": ", 1)[-1])

    dispo = st.selectbox("Disposition (POL-005-S1)", DISPOSITIONS)
    notes = st.text_area("Analyst notes (written rationale)", height=80)
    if st.button("Generate finding", type="primary"):
        extra = []
        if row["KYC_STATUS"] == "EXPIRED":
            extra = ["REG-001-S2"]
        elif row["KYC_STATUS"] == "PENDING":
            extra = ["REG-001-S3"]
        if extra:
            pol = pd.concat([pol, session.sql(
                f"SELECT SECTION_ID, TITLE, SECTION_TITLE, TEXT FROM {T}.POLICY_DOCS "
                f"WHERE SECTION_ID = '{extra[0]}'").to_pandas()])
        f = build_finding(row, ev["TXN_ID"].tolist(), pol.to_dict("records"), dispo, notes)
        session.sql(f"""
            INSERT INTO {T}.FINDINGS
            (FINDING_ID, ALERT_ID, RULE_ID, ACCOUNT_ID, CUSTOMER_ID, SEVERITY, DISPOSITION,
             RISK_ASSESSMENT, RECOMMENDED_ACTION, POLICY_SECTIONS, EVIDENCE_TXN_IDS,
             FINDING_TEXT, ANALYST_NOTES, STATUS, CREATED_BY)
            SELECT UUID_STRING(), '{esc(pick)}', '{esc(row['RULE_ID'])}', '{esc(row['ACCOUNT_ID'])}',
                   '{esc(row['CUSTOMER_ID'])}', '{esc(row['SEVERITY'])}', '{esc(dispo)}',
                   '{esc(f['risk'])}', '{esc(f['action'])}', '{esc(', '.join(f['sections']))}',
                   '{esc(', '.join(ev['TXN_ID']))}', '{esc(f['report'])}', '{esc(notes)}',
                   'DRAFT', CURRENT_USER()
        """).collect()
        load_alerts.clear()
        st.success("Finding saved to FINDINGS (status DRAFT).")
        st.markdown(f["report"])
        st.download_button("Download report (.md)", f["report"], file_name=f"finding_{pick}.md")

# ----------------------------- ask the copilot ---------------------------
with tab3:
    st.caption("Powered by the RISK_COPILOT Cortex Agent: data (Analyst) + policies (Search).")
    if "chat" not in st.session_state:
        st.session_state["chat"] = []
    for m in st.session_state["chat"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    prompt = st.chat_input("Ask about alerts, customers, evidence or policy") \
        or st.session_state.pop("queued", None)
    if prompt:
        st.session_state["chat"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    resp = call_agent(st.session_state["chat"])
                    raw = resp.get("content", "")
                    if resp.get("status", 500) >= 400:
                        answer = f"Agent call failed (HTTP {resp.get('status')}). See raw response below."
                    else:
                        answer = parse_agent_response(raw) or "No text found. See raw response below."
                except Exception as e:  # keep the app alive during the demo
                    raw, answer = str(e), f"Could not call the agent: {e}"
            st.markdown(answer)
            with st.expander("Raw response (debug)"):
                st.code(str(raw)[:6000])
        st.session_state["chat"].append({"role": "assistant", "content": answer})