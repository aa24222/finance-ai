# Trust Spend 💰

An AI-powered financial coach that transforms transaction data into actionable insights.

**Live Demo:** https://finance-ai-five-navy.vercel.app/

## Features

-  **Dashboard** — Income, spending, and balance at a glance
-  **Spending Habits** — Detects repetitive purchases and savings potential
-  **Subscription Tracker** — Finds recurring charges and flags overlaps
-  **Anomaly Detection** — ML-powered unusual transaction flagging (Isolation Forest)
-  **Goal Forecaster** — Predicts savings trajectory with Linear Regression
-  **AI Coach** — Personalized advice powered by Claude API

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, Vite, Recharts |
| Backend | Flask, Pandas, scikit-learn |
| Auth | Supabase (JWT/ES256) |
| AI | Claude API (Anthropic) |
| Hosting | Vercel, Render |

## Documentation

See [DESIGN_DOC.md](./DESIGN_DOC.md) for detailed architecture and implementation.

## Quick Start

```bash
# Frontend
cd frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
python app.py
```

## Environment Variables

**Frontend (.env)**
```
VITE_SUPABASE_URL=your-supabase-url
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_BASE=http://localhost:5000/api
```

**Backend (.env)**
```
SUPABASE_URL=your-supabase-url
ANTHROPIC_API_KEY=your-api-key
```

## License

MIT
