import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression


class FinancialAnalyzer:
    """
    Smart Financial Coach - Analysis Engine
    Provides AI-powered insights into spending patterns
    """

    def __init__(self, csv_path):
        # Load CSV
        self.df = pd.read_csv(csv_path)

        # Normalize core columns
        self.df['date'] = pd.to_datetime(self.df.get('date'), errors='coerce')
        self.df['amount'] = pd.to_numeric(self.df.get('amount'), errors='coerce')

        # Default tag if missing (normal/subscription/bill)
        if 'transaction_tag' not in self.df.columns:
            self.df['transaction_tag'] = 'normal'
        self.df['transaction_tag'] = (
            self.df['transaction_tag']
            .fillna('normal')
            .astype(str)
            .str.strip()
            .str.lower()
        )

        # Normalize type/category/merchant/description if present
        if 'type' in self.df.columns:
            self.df['type'] = self.df['type'].astype(str).str.strip().str.lower()
        if 'category' in self.df.columns:
            self.df['category'] = self.df['category'].astype(str).str.strip()
        if 'merchant' in self.df.columns:
            self.df['merchant'] = self.df['merchant'].astype(str).str.strip()
        if 'description' in self.df.columns:
            self.df['description'] = self.df['description'].astype(str).str.strip()

        # Drop unusable rows + keep deterministic ordering
        self.df = self.df.dropna(subset=['date', 'amount'])
        self.df = self.df.sort_values('date').reset_index(drop=True)

    def get_summary_stats(self):
        """Get overall financial summary"""
        df = self.df
        if df.empty:
            return {
                'total_income': 0.0,
                'total_spending': 0.0,
                'net_balance': 0.0,
                'avg_monthly_spending': 0.0,
                'avg_daily_spending': 0.0,
                'date_range': {'start': None, 'end': None, 'days': 0},
            }

        # Separate credits/debits
        income = float(df.loc[df['type'] == 'credit', 'amount'].sum())
        spending = float(df.loc[df['type'] == 'debit', 'amount'].abs().sum())

        # Time window math
        days = int((df['date'].max() - df['date'].min()).days)
        months = max(1.0, days / 30.0)

        return {
            'total_income': income,
            'total_spending': spending,
            'net_balance': float(income - spending),
            'avg_monthly_spending': float(spending / months),
            'avg_daily_spending': float(spending / max(1, days)),
            'date_range': {
                'start': str(df['date'].min().date()),
                'end': str(df['date'].max().date()),
                'days': int(days),
            },
        }

    def get_spending_by_category(self):
        """Get spending breakdown by category"""
        df = self.df
        debit = df[df['type'] == 'debit']
        if debit.empty:
            return []

        # Sum by category
        spending = debit.groupby('category')['amount'].sum().abs()
        total = float(spending.sum()) or 0.0

        out = []
        for category, amount in spending.sort_values(ascending=False).items():
            amt = float(amount)
            out.append({
                'category': category,
                'amount': amt,
                'percentage': float((amt / total) * 100) if total > 0 else 0.0,
            })
        return out

    # ========== FEATURE 1: Spending Habits Detection ==========
    def detect_spending_habits(self):
        """
        Finds frequent small-transaction habits using data-driven analysis
        Detects patterns like coffee shops, fast food, convenience stores, etc.
        """
        df = self.df

        # Focus on "habit-sized" debits and ignore bills/subscriptions
        small = df[
            (df['type'] == 'debit') &
            (df['amount'].abs().between(3, 25)) &
            (~df['transaction_tag'].isin(['bill', 'subscription']))
        ]
        if small.empty:
            return None

        # Merchant rollup
        stats = small.groupby('merchant').agg(
            visits=('amount', 'count'),
            avg_amount=('amount', 'mean'),
            total=('amount', 'sum'),
        ).reset_index()
        stats['total'] = stats['total'].abs()

        # Needs repetition to count as a habit
        stats = stats[stats['visits'] >= 3]
        if stats.empty:
            return None

        # Pick the strongest habit signal
        top = stats.sort_values(['visits', 'total'], ascending=False).iloc[0]

        days = int((df['date'].max() - df['date'].min()).days) if not df.empty else 0
        months = max(1.0, days / 30.0)
        weeks = max(1.0, days / 7.0)

        monthly_avg = float(top['total'] / months)
        weekly_frequency = float(top['visits'] / weeks)
        annual_projection = float(monthly_avg * 12)
        potential_savings = float(annual_projection * 0.5)

        return {
            'habit_type': top['merchant'],
            'total_spent': float(top['total']),
            'num_visits': int(top['visits']),
            'avg_per_visit': float(top['avg_amount']),
            'monthly_average': monthly_avg,
            'weekly_frequency': weekly_frequency,
            'annual_projection': annual_projection,
            'potential_savings': potential_savings,
            'insight': (
                f"You spent ${top['total']:.2f} at {top['merchant']} "
                f"({int(top['visits'])} visits at ${top['avg_amount']:.2f} per visit). "
                f"Cutting back 50% could save ${potential_savings:.0f}/year!"
            ),
        }

    # ========== AI FEATURE: Anomaly Detection ==========
    def detect_anomalies(self, contamination=0.05):
        """
        Uses Isolation Forest (AI) to detect unusual transactions
        Identifies fraud, errors, or unexpected charges automatically
        """
        df = self.df
        tx = df[(df['type'] == 'debit') & df['amount'].notna()].copy()
        if tx.shape[0] < 10:
            return None

        # Work in absolute space for modeling
        tx['amount_abs'] = tx['amount'].abs()

        # Exclude bills/subscriptions from anomaly modeling
        model_tx = tx[~tx['transaction_tag'].isin(['bill', 'subscription'])].copy()
        if model_tx.shape[0] < 10:
            return {
                'found': False,
                'message': 'Not enough non-recurring data for anomaly detection',
                'ml_model': 'Isolation Forest',
                'recurring_bills': self._get_tagged_bills(tx),
            }

        # Feature engineering
        model_tx = model_tx.sort_values('date').reset_index(drop=True)
        model_tx['day_of_week'] = model_tx['date'].dt.dayofweek
        model_tx['day_of_month'] = model_tx['date'].dt.day

        # Merchant history (shifted to avoid leakage)
        model_tx['merchant_avg'] = (
            model_tx.groupby('merchant')['amount_abs']
            .expanding().mean().shift(1)
            .reset_index(level=0, drop=True)
        )
        model_tx['merchant_std'] = (
            model_tx.groupby('merchant')['amount_abs']
            .expanding().std().shift(1)
            .reset_index(level=0, drop=True)
        )
        model_tx['z_score'] = (
            (model_tx['amount_abs'] - model_tx['merchant_avg']) /
            (model_tx['merchant_std'] + 1e-5)
        ).abs()

        # Model matrix
        X = model_tx[['amount_abs', 'day_of_week', 'day_of_month', 'z_score']].copy()
        X['log_amount'] = np.log1p(X['amount_abs'])
        X = X.drop(columns=['amount_abs'])
        X = X.fillna(X.mean(numeric_only=True))

        # Train model
        iso = IsolationForest(
            contamination=float(contamination),
            random_state=42,
            n_estimators=200,
        )
        model_tx['anomaly'] = iso.fit_predict(X)
        model_tx['anomaly_score'] = iso.score_samples(X)

        anomalies = model_tx[model_tx['anomaly'] == -1].copy()
        recurring_bills = self._get_tagged_bills(tx)

        if anomalies.empty:
            return {
                'found': False,
                'message': 'No unusual transactions detected - all spending appears normal',
                'ml_model': 'Isolation Forest',
                'recurring_bills': recurring_bills,
            }

        # Rank most unusual first (lower score = more anomalous)
        anomalies = anomalies.sort_values('anomaly_score')

        # Global thresholds for explanations
        median_amount = float(model_tx['amount_abs'].median())
        q85 = float(model_tx['amount_abs'].quantile(0.85))
        q95 = float(model_tx['amount_abs'].quantile(0.95))

        s1 = float(np.quantile(anomalies['anomaly_score'], 0.33))
        s2 = float(np.quantile(anomalies['anomaly_score'], 0.66))

        # Build response list
        anomaly_list = []
        for _, row in anomalies.head(10).iterrows():
            reasons = []
            amount = float(row['amount_abs'])
            score = float(row['anomaly_score'])

            # Compare against global typical spend
            if amount > q85:
                pct = ((amount - median_amount) / median_amount * 100) if median_amount > 0 else 0
                reasons.append(f"{pct:.0f}% above typical spending")

            # Compare against this merchant's historical baseline
            if pd.notna(row['merchant_avg']) and float(row['merchant_avg']) > 0 and amount > float(row['merchant_avg']) * 2:
                pct = ((amount - float(row['merchant_avg'])) / float(row['merchant_avg']) * 100)
                reasons.append(f"{pct:.0f}% above normal for {row['merchant']}")

            # Compare against category baseline (if enough samples)
            cat_tx = model_tx[model_tx['category'] == row['category']]
            if len(cat_tx) >= 5:
                cat_avg = float(cat_tx['amount_abs'].mean())
                if cat_avg > 0 and amount > cat_avg * 2:
                    reasons.append(f"high amount for {row['category']} category")

            if not reasons:
                reasons.append("unusual pattern detected by AI")

            # Score-to-confidence mapping
            if score <= s1:
                confidence = 'high'
            elif score <= s2:
                confidence = 'medium'
            else:
                confidence = 'low'

            anomaly_list.append({
                'date': row['date'].date().isoformat(),
                'merchant': row['merchant'],
                'amount': amount,
                'category': row['category'],
                'description': row.get('description', ''),
                'anomaly_score': score,
                'confidence': confidence,
                'reasons': reasons,
                'severity': 'high' if amount > q95 else 'medium' if amount > q85 else 'low',
            })

        # Summary stats
        total_anomaly_amount = float(anomalies['amount_abs'].sum(skipna=True))
        pct_of_transactions = float((len(anomalies) / max(1, len(model_tx))) * 100)

        insight = (
            f"AI detected {len(anomalies)} unusual transactions "
            f"({pct_of_transactions:.1f}% of all non-recurring spending). "
            f"Largest anomaly: ${anomaly_list[0]['amount']:.2f} "
            f"at {anomaly_list[0]['merchant']}."
        )

        return {
            'found': True,
            'anomalies': anomaly_list,
            'total_anomalies': int(len(anomalies)),
            'total_amount': float(total_anomaly_amount),
            'percentage_of_transactions': float(pct_of_transactions),
            'insight': insight,
            'ml_model': 'Isolation Forest (unsupervised anomaly detection)',
            'contamination_rate': float(contamination),
            'recurring_bills': recurring_bills,
        }

    def _get_tagged_bills(self, debit_df):
        # Summarize recurring bills using the CSV tag
        bills = debit_df[debit_df['transaction_tag'] == 'bill'].copy()
        if bills.empty:
            return []

        bills['month'] = bills['date'].dt.to_period('M')
        bills['amount_rounded'] = bills['amount'].abs().round(2)

        grouped = bills.groupby(['merchant', 'amount_rounded']).agg(
            months_count=('month', 'nunique'),
            occurrences=('amount', 'count'),
        ).reset_index()

        out = []
        for _, r in grouped.sort_values('months_count', ascending=False).head(10).iterrows():
            out.append({
                'merchant': r['merchant'],
                'amount': float(r['amount_rounded']),
                'months_count': int(r['months_count']),
                'occurrences': int(r['occurrences']),
            })
        return out

    # ========== FEATURE 2: Subscription Detector ==========
    def detect_subscriptions(self):
        """
        Uses transaction labels to identify subscriptions.
        """
        df = self.df
        debit = df[df['type'] == 'debit'].copy()
        if debit.empty:
            return {
                'subscriptions': [],
                'total_count': 0,
                'total_monthly_cost': 0.0,
                'total_annual_cost': 0.0,
                'unused_count': 0,
                'unused_monthly_waste': 0.0,
                'unused_annual_waste': 0.0,
                'insight': 'No subscriptions detected.',
            }

        subs = debit[debit['transaction_tag'] == 'subscription'].copy()
        if subs.empty:
            return {
                'subscriptions': [],
                'total_count': 0,
                'total_monthly_cost': 0.0,
                'total_annual_cost': 0.0,
                'unused_count': 0,
                'unused_monthly_waste': 0.0,
                'unused_annual_waste': 0.0,
                'insight': 'No subscriptions detected.',
            }

        subs['amount_abs'] = subs['amount'].abs()
        max_date = subs['date'].max()

        results = []
        total_monthly = 0.0
        unused_monthly = 0.0

        for merchant, g in subs.groupby('merchant'):
            # Use median to tolerate small price changes
            g = g.sort_values('date')
            monthly_cost = float(np.median(g['amount_abs']))
            annual_cost = float(monthly_cost * 12)

            # Recentness heuristic (stale subscriptions look "unused")
            last_charge = g['date'].max()
            days_since = int((max_date - last_charge).days)

            # Trial → paid signal (multiple distinct price points)
            amounts = g['amount_abs'].round(2)
            uniq = sorted(amounts.unique().tolist())
            trial_to_paid = False
            if len(uniq) >= 2:
                lo, hi = float(uniq[0]), float(uniq[-1])
                if lo == 0.0 or (hi > 0 and lo / hi <= 0.5):
                    trial_to_paid = True

            # Minimal "cancel suggestion" logic (demo-friendly)
            likely_unused = (days_since >= 20) or (len(g) <= 1)


            results.append({
                'merchant': merchant,
                'monthly_cost': monthly_cost,
                'annual_cost': annual_cost,
                'occurrences': int(len(g)),
                'last_charge_date': last_charge.date().isoformat(),
                'trial_to_paid': bool(trial_to_paid),
                'likely_unused': bool(likely_unused),
                'tag': 'SUBSCRIPTION',
            })

            total_monthly += monthly_cost
            if likely_unused:
                unused_monthly += monthly_cost

        # Sort by monthly impact
        results.sort(key=lambda r: -r['monthly_cost'])

        unused_count = sum(1 for r in results if r['likely_unused'])
        trial_count = sum(1 for r in results if r.get('trial_to_paid'))

        extra = []
        if trial_count:
            extra.append(f"{trial_count} look like trial→paid conversions")
        if unused_count:
            extra.append(f"{unused_count} may be worth reviewing")
        extra_text = (" (" + "; ".join(extra) + ")") if extra else ""

        return {
            'subscriptions': results,
            'total_count': int(len(results)),
            'total_monthly_cost': float(total_monthly),
            'total_annual_cost': float(total_monthly * 12.0),
            'unused_count': int(unused_count),
            'unused_monthly_waste': float(unused_monthly),
            'unused_annual_waste': float(unused_monthly * 12.0),
            'insight': f"Found {len(results)} subscriptions totaling ${total_monthly:.2f}/month{extra_text}.",
        }

    # ========== FEATURE 3: Goal Forecasting ==========
    def forecast_goal(self, goal_amount, goal_months):
        """
        Uses Linear Regression ML to forecast whether user will reach savings goal
        Provides AI-powered predictions based on spending trends
        """
        df = self.df
        if df.empty:
            return self._forecast_goal_simple(goal_amount, goal_months)

        # Monthly spending
        debit = df[df['type'] == 'debit'].copy()
        debit['month'] = debit['date'].dt.to_period('M')
        monthly_spending = debit.groupby('month')['amount'].sum().abs().reset_index()
        monthly_spending.columns = ['month', 'spending']
        monthly_spending['month_num'] = range(len(monthly_spending))

        # Monthly income
        credit = df[df['type'] == 'credit'].copy()
        credit['month'] = credit['date'].dt.to_period('M')
        monthly_income = credit.groupby('month')['amount'].sum().reset_index()
        monthly_income.columns = ['month', 'income']

        # Merge and compute savings
        monthly = monthly_spending.merge(monthly_income, on='month', how='left')
        monthly['income'] = monthly['income'].fillna(monthly['income'].mean() if monthly['income'].notna().any() else 0.0)
        monthly['savings'] = monthly['income'] - monthly['spending']

        # Need at least 2 months for a trend
        if len(monthly) < 2:
            return self._forecast_goal_simple(goal_amount, goal_months)

        # Fit savings trend (simple, demo-friendly)
        X = monthly[['month_num']].values
        y_spending = monthly['spending'].values
        y_savings = monthly['savings'].values

        model_spending = LinearRegression().fit(X, y_spending)
        r2_score = float(model_spending.score(X, y_spending))

        model_savings = LinearRegression().fit(X, y_savings)

        future = np.arange(len(monthly), len(monthly) + int(goal_months)).reshape(-1, 1)
        predicted_savings = model_savings.predict(future)

        current_monthly_savings = float(np.mean(predicted_savings))
        projected_total_savings = float(np.sum(predicted_savings))

        will_reach_goal = bool(projected_total_savings >= float(goal_amount))
        shortfall = float(max(0.0, float(goal_amount) - projected_total_savings))

        monthly_income_val = float(monthly['income'].mean())
        monthly_spending_avg = float(monthly['spending'].mean())

        required_monthly_savings = float(goal_amount) / max(1, int(goal_months))
        monthly_gap = required_monthly_savings - current_monthly_savings

        # Recommendations
        recommendations = []
        total_potential_savings = 0.0

        spending_data = self.detect_spending_habits()
        if spending_data and spending_data['monthly_average'] > 40:
            saving = float(spending_data['monthly_average'] * 0.5)
            recommendations.append({
                'action': f"Reduce {spending_data['habit_type']} visits by 50%",
                'monthly_savings': saving,
                'annual_savings': float(saving * 12),
                'impact_percentage': float(saving / monthly_gap * 100) if monthly_gap > 0 else 100,
                'difficulty': 'Easy',
            })
            total_potential_savings += saving

        subs_data = self.detect_subscriptions()
        if subs_data.get('unused_monthly_waste', 0) > 0:
            saving = float(subs_data['unused_monthly_waste'])
            recommendations.append({
                'action': f"Review/cancel {subs_data['unused_count']} subscription(s)",
                'monthly_savings': saving,
                'annual_savings': float(saving * 12),
                'impact_percentage': float(saving / monthly_gap * 100) if monthly_gap > 0 else 100,
                'difficulty': 'Easy',
            })
            total_potential_savings += saving

        dining_cat = next((c for c in self.get_spending_by_category() if c['category'] == 'Dining Out'), None)
        if dining_cat:
            days = int((df['date'].max() - df['date'].min()).days)
            months = max(1.0, days / 30.0)
            monthly_dining = float(dining_cat['amount'] / months)
            if monthly_dining > 150:
                saving = float(monthly_dining * 0.25)
                recommendations.append({
                    'action': 'Cook at home more (reduce dining out 25%)',
                    'monthly_savings': saving,
                    'annual_savings': float(saving * 12),
                    'impact_percentage': float(saving / monthly_gap * 100) if monthly_gap > 0 else 100,
                    'difficulty': 'Medium',
                })
                total_potential_savings += saving

        # Projection with changes
        new_monthly_savings = current_monthly_savings + total_potential_savings
        success_probability = (
            min(100.0, (new_monthly_savings / required_monthly_savings) * 100)
            if required_monthly_savings > 0 else 100.0
        )

        new_projected_total = float(np.sum(predicted_savings + total_potential_savings))
        will_reach_with_changes = bool(new_projected_total >= float(goal_amount))

        # Confidence label from spending fit quality
        if r2_score >= 0.8:
            confidence, confidence_pct = 'high', 90
        elif r2_score >= 0.6:
            confidence, confidence_pct = 'medium', 75
        else:
            confidence, confidence_pct = 'low', 60

        return {
            'goal_amount': float(goal_amount),
            'goal_months': int(goal_months),
            'current_monthly_income': float(monthly_income_val),
            'current_monthly_spending': float(monthly_spending_avg),
            'current_monthly_savings': float(current_monthly_savings),
            'required_monthly_savings': float(required_monthly_savings),
            'monthly_gap': float(monthly_gap),
            'projected_total': float(projected_total_savings),
            'shortfall': float(shortfall),
            'will_reach_goal': will_reach_goal,
            'recommendations': recommendations,
            'total_potential_savings': float(total_potential_savings),
            'new_monthly_savings': float(new_monthly_savings),
            'new_projected_total': float(new_projected_total),
            'will_reach_with_changes': will_reach_with_changes,
            'success_probability': float(success_probability),
            'ml_model': 'Linear Regression',
            'model_accuracy': float(r2_score),
            'confidence_level': confidence,
            'confidence_percentage': confidence_pct,
            'insight': self._generate_goal_insight_ml(
                current_monthly_savings,
                required_monthly_savings,
                total_potential_savings,
                will_reach_goal,
                will_reach_with_changes,
                confidence,
                r2_score,
            ),
        }

    def _forecast_goal_simple(self, goal_amount, goal_months):
        """
        Fallback to simple averaging if not enough data for ML
        """
        df = self.df
        if df.empty:
            required = float(goal_amount) / max(1, int(goal_months))
            return {
                'goal_amount': float(goal_amount),
                'goal_months': int(goal_months),
                'current_monthly_income': 0.0,
                'current_monthly_spending': 0.0,
                'current_monthly_savings': 0.0,
                'required_monthly_savings': required,
                'monthly_gap': required,
                'projected_total': 0.0,
                'shortfall': float(goal_amount),
                'will_reach_goal': False,
                'recommendations': [],
                'total_potential_savings': 0.0,
                'new_monthly_savings': 0.0,
                'new_projected_total': 0.0,
                'will_reach_with_changes': False,
                'success_probability': 50.0,
                'ml_model': 'Simple average (insufficient data for ML)',
                'model_accuracy': 0.0,
                'confidence_level': 'low',
                'confidence_percentage': 50,
                'insight': 'Not enough historical data for ML prediction. Showing simple average.',
            }

        # Compute averages over the observed window
        days = int((df['date'].max() - df['date'].min()).days)
        months = max(1.0, days / 30.0)

        total_income = float(df.loc[df['type'] == 'credit', 'amount'].sum())
        total_spending = float(df.loc[df['type'] == 'debit', 'amount'].abs().sum())

        monthly_income = total_income / months
        monthly_spending = total_spending / months
        current_monthly_savings = monthly_income - monthly_spending

        required_monthly_savings = float(goal_amount) / max(1, int(goal_months))
        monthly_gap = required_monthly_savings - current_monthly_savings

        projected_total_savings = current_monthly_savings * int(goal_months)
        will_reach_goal = bool(projected_total_savings >= float(goal_amount))
        shortfall = float(max(0.0, float(goal_amount) - projected_total_savings))

        return {
            'goal_amount': float(goal_amount),
            'goal_months': int(goal_months),
            'current_monthly_income': float(monthly_income),
            'current_monthly_spending': float(monthly_spending),
            'current_monthly_savings': float(current_monthly_savings),
            'required_monthly_savings': float(required_monthly_savings),
            'monthly_gap': float(monthly_gap),
            'projected_total': float(projected_total_savings),
            'shortfall': float(shortfall),
            'will_reach_goal': will_reach_goal,
            'recommendations': [],
            'total_potential_savings': 0.0,
            'new_monthly_savings': float(current_monthly_savings),
            'new_projected_total': float(projected_total_savings),
            'will_reach_with_changes': will_reach_goal,
            'success_probability': 50.0,
            'ml_model': 'Simple average (insufficient data for ML)',
            'model_accuracy': 0.0,
            'confidence_level': 'low',
            'confidence_percentage': 50,
            'insight': 'Not enough historical data for ML prediction. Showing simple average.',
        }

    def _generate_goal_insight_ml(self, current, required, potential, reach_now, reach_with_changes, confidence, r2_score):
        """Generate human-readable insight for ML-based goal forecast"""
        gap = required - current
        confidence_text = f"ML model shows {confidence} confidence ({r2_score*100:.0f}% accuracy). "

        if reach_now:
            return confidence_text + "Great news! You're already on track to reach your goal. Keep it up!"
        if reach_with_changes:
            percent = (potential / gap * 100) if gap > 0 else 0
            return (
                confidence_text +
                f"You're currently ${gap:.2f}/month short of your goal. "
                f"Our AI recommendations would save ${potential:.2f}/month ({percent:.0f}% of what you need), "
                "putting you on track to reach your goal!"
            )
        return (
            confidence_text +
            f"You need to save ${required:.2f}/month but currently save ${current:.2f}/month. "
            f"Our AI recommendations could save ${potential:.2f}/month, getting you closer to your goal!"
        )

    def get_timeline_data(self):
        """Get daily spending for timeline charts"""
        df = self.df[self.df['type'] == 'debit'].copy()
        if df.empty:
            return []

        daily = df.groupby(df['date'].dt.date)['amount'].sum().abs()
        return [{'date': str(d), 'amount': float(a)} for d, a in daily.items()]

    def get_category_trends(self):
        """Get spending trends by category over time"""
        df_debit = self.df[self.df['type'] == 'debit'].copy()
        if df_debit.empty:
            return []

        df_debit['month'] = df_debit['date'].dt.to_period('M')
        monthly = df_debit.groupby(['month', 'category'])['amount'].sum().abs().reset_index()
        monthly['month'] = monthly['month'].astype(str)
        return monthly.to_dict('records')
