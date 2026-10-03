"""
Synthetic banking data generator (Risk, Fraud & Regulatory Copilot).
Run:  pip install faker pandas
      python generate_data.py
Outputs CSVs in ./data (load them into Snowflake via Snowsight or COPY INTO).
All data is fake. No real PII.
"""
import os
import random
from datetime import timedelta

import pandas as pd
from faker import Faker

SEED = 42
N_CUSTOMERS = 2000
N_TXNS = 50000

fake = Faker("en_IN")  # Indian names/cities; change to en_US etc. if needed
Faker.seed(SEED)
random.seed(SEED)
os.makedirs("data", exist_ok=True)

# ---------- Customers ----------
customers = pd.DataFrame([{
    "customer_id": f"C{i:05d}",
    "name": fake.name(),
    "city": fake.city(),
    "kyc_status": random.choices(["VERIFIED", "PENDING", "EXPIRED"], [0.85, 0.1, 0.05])[0],
    "risk_rating": random.choices(["LOW", "MEDIUM", "HIGH"], [0.7, 0.22, 0.08])[0],
    "segment": random.choice(["RETAIL", "SME", "CORPORATE"]),
    "onboarded_on": fake.date_between("-8y", "-6m"),
} for i in range(1, N_CUSTOMERS + 1)])

# ---------- Accounts (1 or 2 per customer) ----------
accounts = []
for cid in customers.customer_id:
    for _ in range(random.choice([1, 1, 2])):
        accounts.append({
            "account_id": f"A{len(accounts) + 1:06d}",
            "customer_id": cid,
            "account_type": random.choice(["SAVINGS", "CURRENT", "LOAN"]),
            "balance": round(random.uniform(1_000, 5_000_000), 2),
            "avg_monthly_inflow": round(random.uniform(10_000, 500_000), 2),
        })
accounts = pd.DataFrame(accounts)
acct_ids = accounts.account_id.tolist()

# ---------- Transactions (mostly normal) ----------
channels = ["UPI", "NEFT", "RTGS", "IMPS", "CARD", "ATM", "CASH_DEPOSIT"]
countries = ["IN"] * 95 + ["AE", "SG", "GB", "US", "NG", "KY"]
start = pd.Timestamp("2026-01-01")

def make_txn(acct, ts, amount, channel, country="IN", flag=None):
    return {
        "txn_id": None, "account_id": acct, "txn_ts": ts,
        "amount": round(amount, 2), "channel": channel,
        "counterparty_country": country,
        "merchant_category": random.choice(["GROCERY", "TRAVEL", "UTILITIES", "JEWELLERY", "CRYPTO", "RETAIL"]),
        "injected_pattern": flag,  # ground truth label, handy for evaluating your detector
    }

txns = []
for _ in range(N_TXNS):
    ts = start + timedelta(seconds=random.randint(0, 270 * 86400))
    txns.append(make_txn(random.choice(acct_ids), ts,
                         random.lognormvariate(8, 1.2), random.choice(channels),
                         random.choice(countries)))

# ---------- Inject fraud / AML patterns ----------
# 1) Structuring: many cash deposits just below the 10 lakh reporting threshold
for acct in random.sample(acct_ids, 25):
    base = start + timedelta(days=random.randint(10, 250))
    for k in range(random.randint(4, 8)):
        txns.append(make_txn(acct, base + timedelta(hours=k * 6),
                             random.uniform(900_000, 995_000), "CASH_DEPOSIT", flag="STRUCTURING"))

# 2) Velocity burst: many small transfers in minutes
for acct in random.sample(acct_ids, 25):
    base = start + timedelta(days=random.randint(10, 250))
    for k in range(random.randint(15, 30)):
        txns.append(make_txn(acct, base + timedelta(minutes=k * 2),
                             random.uniform(2_000, 9_000), "UPI", flag="VELOCITY_BURST"))

# 3) Large high-risk-geography transfer
for acct in random.sample(acct_ids, 20):
    txns.append(make_txn(acct, start + timedelta(days=random.randint(10, 250)),
                         random.uniform(2_000_000, 8_000_000), "RTGS",
                         random.choice(["NG", "KY"]), flag="HIGH_RISK_GEO"))

txns = pd.DataFrame(txns).sort_values("txn_ts").reset_index(drop=True)
txns["txn_id"] = [f"T{i:07d}" for i in range(1, len(txns) + 1)]

# ---------- Policy / regulatory text (sectioned, see policy_docs.py) ----------
from policy_docs import build_policy_docs
policy_docs = build_policy_docs()

# ---------- Save ----------
customers.to_csv("data/customers.csv", index=False)
accounts.to_csv("data/accounts.csv", index=False)
txns.to_csv("data/transactions.csv", index=False)
policy_docs.to_csv("data/policy_docs.csv", index=False)

print(f"customers={len(customers)}, accounts={len(accounts)}, transactions={len(txns)}, docs={len(policy_docs)}")
print(txns.injected_pattern.value_counts(dropna=False))