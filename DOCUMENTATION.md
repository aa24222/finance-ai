# Smart Financial Coach
### Design Documentation

---

## 1. Overview

**Problem:** Many people struggle with personal finance due to lack of visibility into their spending. Manual tracking is tedious, and generic budgeting apps fail to inspire lasting behavioral change.

**Solution:** An AI-powered financial coach that transforms raw transaction data into personalized, actionable insights—helping users identify wasteful habits, track subscriptions, detect anomalies, forecast progress toward savings goals, and receive personalized advice from an LLM-powered coach.

---

## 2. Architecture

```
┌─────────────────┐      HTTPS/JWT       ┌─────────────────┐
│                 │ ◄──────────────────► │                 │
│   React + Vite  │                      │   Flask API     │
│   (Vercel)      │                      │   (Render)      │
│                 │                      │                 │
└─────────────────┘                      └────────┬────────┘
         │                                        │
         │ Auth                          ┌────────┴────────┐
         ▼                               │                 │
┌─────────────────┐              ┌───────▼───────┐ ┌───────▼───────┐
│                 │              │  ML Engine    │ │  Claude API   │
│    Supabase     │              │  (scikit)     │ │  (Anthropic)  │
│    (Auth/JWT)   │              │               │ │               │
└─────────────────┘              └───────────────┘ └───────────────┘
```

| Layer | Technology | Hosting |
|-------|------------|---------|
| Frontend | React 18, Vite, Recharts | Vercel |
| Backend | Flask, Pandas, NumPy | Render |
| Auth | Supabase (JWT/ES256) | Supabase Cloud |
| ML | scikit-learn | Render |
| LLM | Claude API (Anthropic) | Anthropic |

---

## 3. AI & Machine Learning Implementation

### Traditional ML Models

| Algorithm | Purpose | Output |
|-----------|---------|--------|
| **Isolation Forest** | Anomaly detection | Flags unusual transactions with explainable reasons |
| **Linear Regression** | Goal forecasting | Predicts savings trajectory with confidence scores |

The anomaly detection model uses feature engineering including log-transformed amounts, day-of-week/month temporal features, merchant-level z-scores, and rolling statistics. The goal forecaster fits separate models for spending and savings trends, using R² score to determine prediction confidence (high/medium/low).

### LLM Integration (Claude API)

The **AI Financial Coach** feature uses Claude's API to provide personalized, conversational financial advice. The system:

1. Aggregates user's financial context (income, spending, habits, subscriptions, anomalies)
2. Constructs a structured prompt with the financial snapshot
3. Sends to Claude API for natural language advice generation
4. Returns 3 specific, actionable tips personalized to the user's data

This represents genuine AI/LLM capability beyond traditional ML, providing human-like financial coaching at scale.

---

## 4. Key Features

**Spending Habits Analysis**
- Identifies recurring discretionary spending (e.g., daily coffee)
- Calculates weekly frequency and average spend
- Shows potential annual savings from 50% reduction

**Subscription Detector**
- Surfaces all recurring charges from transaction history
- Flags underutilized services and overlapping services for review
- Displays subscription burden as % of monthly spending

**Anomaly Detection**
- Uses Isolation Forest to find unusual transactions
- Provides human-readable explanations
- Compares against user's own spending patterns

**Goal Forecaster**
- Users set savings target and timeframe
- ML predicts if goal will be met with confidence scores
- Provides specific recommendations to close shortfall

**AI Financial Coach (NEW)**
- Powered by Claude API (Anthropic)
- Analyzes complete financial picture
- Delivers personalized, actionable advice in natural language
- Adapts recommendations based on detected habits and anomalies

---

## 5. Security & Privacy

| Measure | Implementation |
|---------|----------------|
| Authentication | Supabase JWT with ECC (ES256) signing |
| Token Verification | JWKS public key validation |
| Data Isolation | Per-user directories keyed by user ID |
| API Protection | `@require_auth` decorator on all sensitive endpoints |
| CORS | Restricted to production frontend domain |
| Headers | X-Frame-Options, X-Content-Type-Options, X-XSS-Protection |
| API Keys | Environment variables, never exposed to client |

---

## 6. Future Enhancements

- **Plaid Integration** — Automatic bank account syncing
- **Persistent Storage** — Supabase PostgreSQL for user data
- **Push Notifications** — Alerts for anomalies and goal milestones
- **Conversational Chat** — Multi-turn conversations with AI coach
- **Enhanced ML** — Category-specific budgets, predictive cash flow

---

## Tech Stack Summary

**Frontend:** React 18 • Vite • Recharts • Supabase JS  
**Backend:** Flask • Pandas • NumPy • scikit-learn • PyJWT • Anthropic SDK  
**Infrastructure:** Vercel • Render • Supabase • Anthropic API
