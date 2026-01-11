import random
from datetime import datetime, timedelta
import pandas as pd

random.seed(42)

# Output path (change if you want)
OUT_PATH = "financial_transactions_big.csv"

# Date range
START = datetime(2024, 1, 1)
END   = datetime(2024, 12, 31)

# How many "normal" daily-ish transactions to generate
MIN_TX_PER_DAY = 0
MAX_TX_PER_DAY = 3

# Recurring transactions
SUBSCRIPTIONS = [
    # merchant, description, amount, category, day_of_month
    ("Netflix", "Netflix Subscription", -15.99, "Entertainment", 15),
    ("Spotify", "Spotify Premium", -10.99, "Entertainment", 12),
    ("Headspace", "Headspace Premium", -12.99, "Health", 18),
    ("Amazon Prime Video", "Amazon Prime Membership", -14.99, "Shopping", 20),
    ("Hulu", "Hulu + Live TV", -69.99, "Entertainment", 8),
    ("Planet Fitness", "Planet Fitness Monthly", -24.99, "Fitness", 3),
]

BILLS = [
    # merchant, description, amount, category, day_of_month
    ("Oak Street Apartments", "Rent Payment - Oak Street Apartments", -1650.00, "Housing", 1),
    ("PG&E Electric", "PG&E Electric", -92.00, "Utilities", 5),
    ("Comcast Internet", "Comcast Internet", -79.99, "Utilities", 7),
    ("AT&T Phone", "AT&T Phone", -65.00, "Utilities", 10),
    ("Geico", "Geico Auto Insurance", -165.00, "Insurance", 14),
]

INCOME = [
    # merchant, description, amount, category, day_of_month
    ("ACME Corp", "ACME Corp - Salary Deposit", 4500.00, "Income", 1),
    ("ACME Corp", "ACME Corp - Salary Deposit", 4500.00, "Income", 15),
]

# Normal spend merchants (category, merchant, description template, min, max)
NORMAL_SPEND = [
    ("Food & Drink", "Starbucks", "Starbucks - Coffee", -9.50, -4.50),
    ("Food & Drink", "Dunkin", "Dunkin - Coffee", -9.00, -4.00),
    ("Food & Drink", "Blue Bottle Coffee", "Blue Bottle Coffee - Coffee", -10.50, -5.00),
    ("Food & Drink", "Local Cafe", "Local Cafe - Coffee", -9.00, -4.00),

    ("Groceries", "Safeway", "Safeway", -160.00, -25.00),
    ("Groceries", "Trader Joes", "Trader Joes", -140.00, -20.00),
    ("Groceries", "Whole Foods", "Whole Foods", -180.00, -25.00),
    ("Groceries", "Walmart", "Walmart", -200.00, -15.00),
    ("Groceries", "Target", "Target", -180.00, -10.00),

    ("Dining Out", "Chipotle", "Chipotle", -35.00, -10.00),
    ("Dining Out", "Shake Shack", "Shake Shack", -45.00, -12.00),
    ("Dining Out", "Five Guys", "Five Guys", -55.00, -12.00),
    ("Dining Out", "Pizza Hut", "Pizza Hut", -30.00, -9.00),
    ("Dining Out", "Taco Bell", "Taco Bell", -28.00, -8.00),

    ("Transportation", "Shell", "Shell", -85.00, -30.00),
    ("Transportation", "Chevron", "Chevron", -85.00, -30.00),
    ("Transportation", "Uber", "Uber Ride", -45.00, -10.00),
    ("Transportation", "76 Gas", "76 Gas", -85.00, -30.00),

    ("Shopping", "IKEA", "IKEA", -350.00, -40.00),
    ("Shopping", "H&M", "H&M", -200.00, -20.00),
]

# Large "unusual" debits that should stand out (tagged normal so anomalies can catch them)
UNUSUAL_LARGE = [
    ("Shopping", "Diamond District Jewelers", "Diamond District Purchase", -2200.00),
    ("Travel", "Delta Airlines", "Delta Airlines - Tickets", -1350.00),
    ("Electronics", "Best Buy", "Best Buy - Electronics", -1800.00),
    ("Auto Maintenance", "AutoNation", "AutoNation - Major Repair", -1450.00),
    ("Home Improvement", "Home Depot", "Home Depot - Renovation Supplies", -980.00),
    ("Cash", "ATM Withdrawal", "ATM Withdrawal", -700.00),
]

# Optional: some credits like refunds
REFUNDS = [
    ("Shopping", "Amazon", "Amazon Refund", 120.55),
    ("Travel", "Airbnb", "Airbnb Refund", 240.00),
]

def daterange(start, end):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)

rows = []
txn_counter = 1

def add_row(date, description, amount, tx_type, category, merchant, tag):
    global txn_counter
    rows.append({
        "transaction_id": f"TXN{txn_counter:07d}",
        "date": f"{date.month}/{date.day}/{date.year}",
        "description": description,
        "amount": round(float(amount), 2),
        "type": tx_type,
        "category": category,
        "merchant": merchant,
        "transaction_tag": tag
    })
    txn_counter += 1

# Pick specific days to inject unusual large transactions
all_days = list(daterange(START, END))
unusual_days = sorted(random.sample(all_days, k=min(len(UNUSUAL_LARGE), 10)))

# Generate
for d in daterange(START, END):
    # Income
    for merchant, desc, amt, cat, dom in INCOME:
        if d.day == dom:
            add_row(d, desc, amt, "credit", cat, merchant, "normal")

    # Bills
    for merchant, desc, amt, cat, dom in BILLS:
        if d.day == dom:
            add_row(d, desc, amt, "debit", cat, merchant, "bill")

    # Subscriptions
    for merchant, desc, amt, cat, dom in SUBSCRIPTIONS:
        if d.day == dom:
            # small amount wobble so it looks real
            wobble = random.choice([0, 0, 0, -0.50, 0.50])
            add_row(d, desc, amt + wobble, "debit", cat, merchant, "subscription")

    # Random daily normal transactions
    count = random.randint(MIN_TX_PER_DAY, MAX_TX_PER_DAY)
    for _ in range(count):
        cat, merchant, desc, lo, hi = random.choice(NORMAL_SPEND)
        amount = random.uniform(lo, hi)

        # Weekend bias: more dining + coffee
        if d.weekday() in (5, 6) and cat in ("Dining Out", "Food & Drink"):
            amount *= random.uniform(1.1, 1.5)

        add_row(d, desc, amount, "debit", cat, merchant, "normal")

    # Inject unusual large transactions on selected days
    if d in unusual_days:
        cat, merchant, desc, amt = random.choice(UNUSUAL_LARGE)
        add_row(d, desc, amt, "debit", cat, merchant, "normal")

    # Occasional refund credits
    if random.random() < 0.015:
        cat, merchant, desc, amt = random.choice(REFUNDS)
        add_row(d, desc, amt, "credit", cat, merchant, "normal")

df = pd.DataFrame(rows).sort_values("date", key=lambda s: pd.to_datetime(s)).reset_index(drop=True)
df.to_csv(OUT_PATH, index=False)

print(f"Wrote {len(df)} rows to {OUT_PATH}")
print(df.head(15).to_string(index=False))
