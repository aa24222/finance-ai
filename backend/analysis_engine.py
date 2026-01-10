import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression

class FinancialAnalyzer:
    """
    Smart Financial Coach - Analysis Engine
    Provides AI-powered insights into spending patterns
    """
    
    def __init__(self, csv_path):
        self.df = pd.read_csv(csv_path)
        self.df['date'] = pd.to_datetime(self.df['date'])
        
    def get_summary_stats(self):
        """Get overall financial summary"""
        total_income = self.df[self.df['type'] == 'credit']['amount'].sum()
        total_spending = abs(self.df[self.df['type'] == 'debit']['amount'].sum())
        
        days = (self.df['date'].max() - self.df['date'].min()).days
        months = max(1, days / 30.0)
        
        return {
            'total_income': float(total_income),
            'total_spending': float(total_spending),
            'net_balance': float(total_income - total_spending),
            'avg_monthly_spending': float(total_spending / months),
            'avg_daily_spending': float(total_spending / max(1, days)),
            'date_range': {
                'start': str(self.df['date'].min().date()),
                'end': str(self.df['date'].max().date()),
                'days': int(days)
            }
        }
    
    def get_spending_by_category(self):
        """Get spending breakdown by category"""
        spending = self.df[self.df['type'] == 'debit'].groupby('category')['amount'].sum().abs()
        total = spending.sum()
        
        result = []
        for category, amount in spending.sort_values(ascending=False).items():
            result.append({
                'category': category,
                'amount': float(amount),
                'percentage': float(amount / total * 100) if total > 0 else 0
            })
        
        return result
    
    # ========== FEATURE 1: Spending Habits Detection ==========
    def detect_spending_habits(self):
        """
        Finds frequent small-transaction habits using data-driven analysis
        Detects patterns like coffee shops, fast food, convenience stores, etc.
        """
        # Filter small transactions ($3-$25 range - typical habit spending)
        small_tx = self.df[(self.df['type'] == 'debit') & 
                           (self.df['amount'].abs() >= 3) & 
                           (self.df['amount'].abs() <= 25)]
        
        if len(small_tx) == 0:
            return None
        
        # Group by merchant to find patterns
        merchant_stats = small_tx.groupby('merchant').agg({
            'amount': ['count', 'mean', 'sum']
        }).reset_index()
        
        merchant_stats.columns = ['merchant', 'visits', 'avg_amount', 'total']
        merchant_stats['total'] = merchant_stats['total'].abs()
        
        # Only consider merchants with 3+ visits (habitual behavior)
        frequent = merchant_stats[merchant_stats['visits'] >= 3]
        
        if len(frequent) == 0:
            return None
        
        # Find the top spending habit (most visits + highest total)
        # Sort by visits first, then by total spent
        top_habit = frequent.sort_values(['visits', 'total'], ascending=False).iloc[0]
        
        # Calculate time-based metrics
        days = (self.df['date'].max() - self.df['date'].min()).days
        months = max(1, days / 30.0)
        weeks = max(1, days / 7.0)
        
        monthly_avg = top_habit['total'] / months
        weekly_frequency = top_habit['visits'] / weeks
        annual_projection = monthly_avg * 12
        
        # Estimate potential savings (50% reduction is reasonable)
        potential_savings = annual_projection * 0.5
        
        return {
            'habit_type': top_habit['merchant'],
            'total_spent': float(top_habit['total']),
            'num_visits': int(top_habit['visits']),
            'avg_per_visit': float(top_habit['avg_amount']),
            'monthly_average': float(monthly_avg),
            'weekly_frequency': float(weekly_frequency),
            'annual_projection': float(annual_projection),
            'potential_savings': float(potential_savings),
            'insight': f"You spent ${top_habit['total']:.2f} at {top_habit['merchant']} " +
                      f"({int(top_habit['visits'])} visits at ${top_habit['avg_amount']:.2f} per visit). " +
                      f"Cutting back 50% could save ${potential_savings:.0f}/year!"
        }
    
    # ========== ML FEATURE: Day Pattern Clustering ==========
    def cluster_spending_days(self, n_clusters=3):
        """
        Uses K-means clustering to identify different spending day patterns
        This is actual machine learning - unsupervised clustering
        """
        # Prepare daily data
        daily_data = self.df[self.df['type'] == 'debit'].copy()
        daily_data['date_only'] = daily_data['date'].dt.date
        
        # Aggregate by day
        daily_stats = daily_data.groupby('date_only').agg({
            'amount': ['sum', 'count'],
            'category': 'nunique'
        }).reset_index()
        
        daily_stats.columns = ['date', 'total_spent', 'num_transactions', 'num_categories']
        daily_stats['total_spent'] = daily_stats['total_spent'].abs()
        
        if len(daily_stats) < n_clusters:
            return None
        
        # Prepare features for clustering
        features = daily_stats[['total_spent', 'num_transactions', 'num_categories']].values
        
        # Standardize features (important for K-means)
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
        
        # Apply K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        daily_stats['cluster'] = kmeans.fit_predict(features_scaled)
        
        # Analyze clusters
        cluster_analysis = []
        for cluster_id in range(n_clusters):
            cluster_days = daily_stats[daily_stats['cluster'] == cluster_id]
            
            avg_spending = cluster_days['total_spent'].mean()
            avg_transactions = cluster_days['num_transactions'].mean()
            num_days = len(cluster_days)
            pct_of_days = (num_days / len(daily_stats)) * 100
            
            # Categorize cluster
            if avg_spending < daily_stats['total_spent'].quantile(0.33):
                label = "Frugal Days"
            elif avg_spending < daily_stats['total_spent'].quantile(0.67):
                label = "Normal Days"
            else:
                label = "Splurge Days"
            
            cluster_analysis.append({
                'cluster_id': int(cluster_id),
                'label': label,
                'avg_spending': float(avg_spending),
                'avg_transactions': float(avg_transactions),
                'num_days': int(num_days),
                'percentage_of_days': float(pct_of_days)
            })
        
        # Sort by average spending
        cluster_analysis.sort(key=lambda x: x['avg_spending'])
        
        # Generate insight
        splurge_cluster = max(cluster_analysis, key=lambda x: x['avg_spending'])
        frugal_cluster = min(cluster_analysis, key=lambda x: x['avg_spending'])
        
        spending_diff = splurge_cluster['avg_spending'] - frugal_cluster['avg_spending']
        
        insight = f"ML analysis identified {n_clusters} spending patterns: " + \
                 f"{splurge_cluster['label']} (${splurge_cluster['avg_spending']:.0f}/day, " + \
                 f"{splurge_cluster['percentage_of_days']:.0f}% of days) vs " + \
                 f"{frugal_cluster['label']} (${frugal_cluster['avg_spending']:.0f}/day, " + \
                 f"{frugal_cluster['percentage_of_days']:.0f}% of days). " + \
                 f"You spend ${spending_diff:.0f} more on splurge days!"
        
        return {
            'n_clusters': n_clusters,
            'clusters': cluster_analysis,
            'total_days': len(daily_stats),
            'insight': insight,
            'ml_model': 'K-means clustering'
        }
    
    # ========== AI FEATURE: Anomaly Detection ==========
    def detect_anomalies(self, contamination=0.05):
        """
        Uses Isolation Forest (AI) to detect unusual transactions
        Identifies fraud, errors, or unexpected charges automatically
        """
        # Get debit transactions only
        transactions = self.df[self.df['type'] == 'debit'].copy()
        
        if len(transactions) < 10:
            return None
        
        # Calculate additional features for better anomaly detection
        transactions['day_of_week'] = transactions['date'].dt.dayofweek
        transactions['day_of_month'] = transactions['date'].dt.day
        transactions['hour'] = transactions['date'].dt.hour if 'time' in transactions.columns else 12
        
        # Calculate historical patterns for each merchant
        merchant_stats = transactions.groupby('merchant')['amount'].agg(['mean', 'std']).reset_index()
        merchant_stats.columns = ['merchant', 'merchant_avg', 'merchant_std']
        transactions = transactions.merge(merchant_stats, on='merchant', how='left')
        
        # Calculate z-score (how unusual compared to that merchant)
        transactions['z_score'] = np.abs((transactions['amount'].abs() - transactions['merchant_avg']) / 
                                         (transactions['merchant_std'] + 1e-5))
        
        # Prepare features for Isolation Forest
        feature_columns = ['amount', 'day_of_week', 'day_of_month', 'z_score']
        
        # Create feature matrix (convert amounts to absolute values)
        features = transactions[feature_columns].copy()
        features['amount'] = features['amount'].abs()
        
        # Fill NaN values
        features = features.fillna(features.mean())
        
        # Train Isolation Forest model
        iso_forest = IsolationForest(
            contamination=contamination,  # Expected % of anomalies
            random_state=42,
            n_estimators=100
        )
        
        # Predict anomalies (-1 = anomaly, 1 = normal)
        transactions['anomaly'] = iso_forest.fit_predict(features)
        transactions['anomaly_score'] = iso_forest.score_samples(features)
        
        # Get anomalies
        anomalies = transactions[transactions['anomaly'] == -1].copy()
        
        if len(anomalies) == 0:
            return {
                'found': False,
                'message': 'No unusual transactions detected - all spending appears normal',
                'ml_model': 'Isolation Forest'
            }
        
        # Sort by anomaly score (most unusual first)
        anomalies = anomalies.sort_values('anomaly_score')
        
        # Analyze anomalies
        anomaly_list = []
        for idx, row in anomalies.head(10).iterrows():  # Top 10 anomalies
            # Determine why it's unusual
            reasons = []
            
            amount_abs = abs(row['amount'])
            
            # Check if amount is unusual
            if amount_abs > transactions['amount'].abs().quantile(0.9):
                pct = ((amount_abs - transactions['amount'].abs().median()) / 
                       transactions['amount'].abs().median() * 100)
                reasons.append(f"{pct:.0f}% above typical spending")
            
            # Check if unusual for this merchant
            if pd.notna(row['merchant_avg']) and amount_abs > row['merchant_avg'] * 2:
                pct = ((amount_abs - row['merchant_avg']) / row['merchant_avg'] * 100)
                reasons.append(f"{pct:.0f}% above normal for {row['merchant']}")
            
            # Check if unusual timing
            if row['day_of_week'] in [5, 6]:  # Weekend
                weekend_avg = transactions[transactions['day_of_week'].isin([5,6])]['amount'].abs().mean()
                if amount_abs > weekend_avg * 1.5:
                    reasons.append("unusual weekend purchase")
            
            # Check category
            category_avg = transactions[transactions['category'] == row['category']]['amount'].abs().mean()
            if amount_abs > category_avg * 2:
                reasons.append(f"high amount for {row['category']} category")
            
            if not reasons:
                reasons.append("unusual pattern detected by AI")
            
            anomaly_list.append({
                'date': str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date']),
                'merchant': row['merchant'],
                'amount': float(amount_abs),
                'category': row['category'],
                'description': row['description'],
                'anomaly_score': float(row['anomaly_score']),
                'reasons': reasons,
                'severity': 'high' if amount_abs > transactions['amount'].abs().quantile(0.95) else 
                           'medium' if amount_abs > transactions['amount'].abs().quantile(0.85) else 'low'
            })
        
        # Calculate statistics
        total_anomaly_amount = anomalies['amount'].abs().sum()
        avg_anomaly = anomalies['amount'].abs().mean()
        pct_of_transactions = (len(anomalies) / len(transactions)) * 100
        
        # Generate insight
        high_severity = [a for a in anomaly_list if a['severity'] == 'high']
        
        if len(high_severity) > 0:
            top_anomaly = high_severity[0]
            insight = f"AI detected {len(anomalies)} unusual transactions ({pct_of_transactions:.1f}% of all spending). " + \
                     f"Most significant: ${top_anomaly['amount']:.2f} at {top_anomaly['merchant']} " + \
                     f"({', '.join(top_anomaly['reasons'][:2])})."
        else:
            insight = f"AI identified {len(anomalies)} minor spending anomalies totaling ${total_anomaly_amount:.2f}. " + \
                     f"These transactions show unusual patterns compared to your typical behavior."
        
        return {
            'found': True,
            'anomalies': anomaly_list,
            'total_anomalies': len(anomalies),
            'total_amount': float(total_anomaly_amount),
            'avg_anomaly_amount': float(avg_anomaly),
            'percentage_of_transactions': float(pct_of_transactions),
            'insight': insight,
            'ml_model': 'Isolation Forest (unsupervised anomaly detection)',
            'contamination_rate': contamination
        }
    
    # ========== FEATURE 2: Subscription Detector ==========
    def detect_subscriptions(self):
        """
        Finds recurring charges that might be subscriptions
        """
        # Group by merchant and amount to find recurring patterns
        debit_transactions = self.df[self.df['type'] == 'debit'].copy()
        
        # Round amounts to handle minor variations
        debit_transactions['amount_rounded'] = debit_transactions['amount'].round(2)
        
        recurring = debit_transactions.groupby(['merchant', 'amount_rounded']).agg({
            'date': 'count',
            'amount': 'first'
        }).reset_index()
        recurring.columns = ['merchant', 'amount_rounded', 'count', 'amount']
        
        # Subscriptions typically appear 3+ times
        subscriptions = recurring[recurring['count'] >= 3].sort_values('count', ascending=False)
        
        results = []
        total_monthly_cost = 0
        unused_waste = 0
        
        # Keywords that suggest unused subscriptions
        unused_keywords = ['fitness', 'gym', 'hulu', 'headspace', 'meditation', 'premium']
        
        for _, row in subscriptions.iterrows():
            monthly_cost = abs(row['amount'])
            annual_cost = monthly_cost * 12
            
            # Heuristic: Check if likely unused
            is_unused = any(keyword in row['merchant'].lower() for keyword in unused_keywords)
            
            sub_info = {
                'merchant': row['merchant'],
                'monthly_cost': float(monthly_cost),
                'annual_cost': float(annual_cost),
                'occurrences': int(row['count']),
                'likely_unused': is_unused,
                'tag': 'UNUSED' if is_unused else 'Active'
            }
            
            results.append(sub_info)
            total_monthly_cost += monthly_cost
            
            if is_unused:
                unused_waste += monthly_cost
        
        return {
            'subscriptions': results,
            'total_count': len(results),
            'total_monthly_cost': float(total_monthly_cost),
            'total_annual_cost': float(total_monthly_cost * 12),
            'unused_count': sum(1 for s in results if s['likely_unused']),
            'unused_monthly_waste': float(unused_waste),
            'unused_annual_waste': float(unused_waste * 12),
            'insight': f"Found {len(results)} recurring subscriptions totaling ${total_monthly_cost:.2f}/month. " +
                      f"${unused_waste:.2f}/month ({len([s for s in results if s['likely_unused']])} subscriptions) " +
                      f"appear to be unused - that's ${unused_waste * 12:.0f}/year!"
        }
    
    # ========== FEATURE 3: Goal Forecasting ==========
    def forecast_goal(self, goal_amount, goal_months):
        """
        Uses Linear Regression ML to forecast whether user will reach savings goal
        Provides AI-powered predictions based on spending trends
        """
        # Prepare monthly spending data for ML model
        df_debit = self.df[self.df['type'] == 'debit'].copy()
        df_debit['month'] = df_debit['date'].dt.to_period('M')
        
        # Calculate monthly spending totals
        monthly_spending = df_debit.groupby('month')['amount'].sum().abs().reset_index()
        monthly_spending.columns = ['month', 'spending']
        monthly_spending['month_num'] = range(len(monthly_spending))
        
        # Calculate monthly income
        df_credit = self.df[self.df['type'] == 'credit'].copy()
        df_credit['month'] = df_credit['date'].dt.to_period('M')
        monthly_income = df_credit.groupby('month')['amount'].sum().reset_index()
        monthly_income.columns = ['month', 'income']
        
        # Merge income and spending
        monthly_data = monthly_spending.merge(monthly_income, on='month', how='left')
        monthly_data['income'] = monthly_data['income'].fillna(monthly_data['income'].mean())
        monthly_data['savings'] = monthly_data['income'] - monthly_data['spending']
        
        # Need at least 2 months of data for ML
        if len(monthly_data) < 2:
            # Fallback to simple average if not enough data
            return self._forecast_goal_simple(goal_amount, goal_months)
        
        # Train Linear Regression model on spending trend
        X_spending = monthly_data[['month_num']].values
        y_spending = monthly_data['spending'].values
        
        model_spending = LinearRegression()
        model_spending.fit(X_spending, y_spending)
        
        # Calculate model accuracy (R² score)
        r2_score = model_spending.score(X_spending, y_spending)
        
        # Train model on savings trend (if we have income data)
        if monthly_data['income'].notna().sum() > 0:
            y_savings = monthly_data['savings'].values
            model_savings = LinearRegression()
            model_savings.fit(X_spending, y_savings)
            savings_r2 = model_savings.score(X_spending, y_savings)
        else:
            model_savings = None
            savings_r2 = 0
        
        # Predict future months
        future_months = np.array(range(len(monthly_data), len(monthly_data) + goal_months)).reshape(-1, 1)
        predicted_spending = model_spending.predict(future_months)
        
        if model_savings is not None:
            predicted_savings = model_savings.predict(future_months)
            current_monthly_savings = float(np.mean(predicted_savings))
        else:
            # Use income - predicted spending
            avg_income = float(monthly_data['income'].mean())
            avg_predicted_spending = float(predicted_spending.mean())
            current_monthly_savings = avg_income - avg_predicted_spending
            predicted_savings = [avg_income - spend for spend in predicted_spending]
        
        # ML-based projection
        projected_total_savings = float(sum(predicted_savings))
        will_reach_goal = bool(projected_total_savings >= goal_amount)
        shortfall = float(max(0, goal_amount - projected_total_savings))
        
        # Current metrics
        monthly_income = float(monthly_data['income'].mean())
        monthly_spending_avg = float(monthly_data['spending'].mean())
        
        # What's needed for goal
        required_monthly_savings = goal_amount / goal_months
        monthly_gap = required_monthly_savings - current_monthly_savings
        
        # Generate smart recommendations
        recommendations = []
        total_potential_savings = 0
        
        # Recommendation 1: Spending Habits
        spending_data = self.detect_spending_habits()
        if spending_data and spending_data['monthly_average'] > 40:
            reduction = 0.5  # 50% reduction
            saving = spending_data['monthly_average'] * reduction
            recommendations.append({
                'action': f"Reduce {spending_data['habit_type']} visits by 50%",
                'monthly_savings': float(saving),
                'annual_savings': float(saving * 12),
                'impact_percentage': float(saving / monthly_gap * 100) if monthly_gap > 0 else 100,
                'difficulty': 'Easy'
            })
            total_potential_savings += saving
        
        # Recommendation 2: Subscriptions
        subs_data = self.detect_subscriptions()
        if subs_data and subs_data['unused_monthly_waste'] > 0:
            saving = subs_data['unused_monthly_waste']
            recommendations.append({
                'action': f"Cancel {subs_data['unused_count']} unused subscription(s)",
                'monthly_savings': float(saving),
                'annual_savings': float(saving * 12),
                'impact_percentage': float(saving / monthly_gap * 100) if monthly_gap > 0 else 100,
                'difficulty': 'Easy'
            })
            total_potential_savings += saving
        
        # Recommendation 3: Dining
        categories = self.get_spending_by_category()
        dining_cat = next((c for c in categories if c['category'] == 'Dining Out'), None)
        if dining_cat:
            days = (self.df['date'].max() - self.df['date'].min()).days
            months = max(1, days / 30.0)
            monthly_dining = dining_cat['amount'] / months
            if monthly_dining > 150:
                reduction = 0.25  # 25% reduction
                saving = monthly_dining * reduction
                recommendations.append({
                    'action': 'Cook at home more (reduce dining out 25%)',
                    'monthly_savings': float(saving),
                    'annual_savings': float(saving * 12),
                    'impact_percentage': float(saving / monthly_gap * 100) if monthly_gap > 0 else 100,
                    'difficulty': 'Medium'
                })
                total_potential_savings += saving
        
        # Calculate success probability with ML predictions
        new_monthly_savings = current_monthly_savings + total_potential_savings
        success_probability = min(100, (new_monthly_savings / required_monthly_savings * 100)) if required_monthly_savings > 0 else 100
        
        # New ML-based projection with recommendations
        new_predicted_savings = [s + total_potential_savings for s in predicted_savings]
        new_projected_total = float(sum(new_predicted_savings))
        will_reach_with_changes = bool(new_projected_total >= goal_amount)
        
        # Determine confidence level based on R² score
        if r2_score >= 0.8:
            confidence = 'high'
            confidence_pct = 90
        elif r2_score >= 0.6:
            confidence = 'medium'
            confidence_pct = 75
        else:
            confidence = 'low'
            confidence_pct = 60
        
        return {
            'goal_amount': float(goal_amount),
            'goal_months': int(goal_months),
            'current_monthly_income': float(monthly_income),
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
                r2_score
            )
        }
    
    def _forecast_goal_simple(self, goal_amount, goal_months):
        """
        Fallback to simple averaging if not enough data for ML
        """
        days = (self.df['date'].max() - self.df['date'].min()).days
        months = max(1, days / 30.0)
        
        total_income = self.df[self.df['type'] == 'credit']['amount'].sum()
        total_spending = abs(self.df[self.df['type'] == 'debit']['amount'].sum())
        
        monthly_income = total_income / months
        monthly_spending = total_spending / months
        current_monthly_savings = monthly_income - monthly_spending
        
        required_monthly_savings = goal_amount / goal_months
        monthly_gap = required_monthly_savings - current_monthly_savings
        
        projected_total_savings = current_monthly_savings * goal_months
        will_reach_goal = bool(projected_total_savings >= goal_amount)
        shortfall = float(max(0, goal_amount - projected_total_savings))
        
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
            'total_potential_savings': 0,
            'new_monthly_savings': float(current_monthly_savings),
            'new_projected_total': float(projected_total_savings),
            'will_reach_with_changes': will_reach_goal,
            'success_probability': 50.0,
            'ml_model': 'Simple average (insufficient data for ML)',
            'model_accuracy': 0.0,
            'confidence_level': 'low',
            'confidence_percentage': 50,
            'insight': 'Not enough historical data for ML prediction. Showing simple average.'
        }
    
    def _generate_goal_insight_ml(self, current, required, potential, reach_now, reach_with_changes, confidence, r2_score):
        """Generate human-readable insight for ML-based goal forecast"""
        gap = required - current
        
        confidence_text = f"ML model shows {confidence} confidence ({r2_score*100:.0f}% accuracy). "
        
        if reach_now:
            return confidence_text + f"Great news! You're already on track to reach your goal. Keep it up!"
        elif reach_with_changes:
            percent = (potential / gap * 100) if gap > 0 else 0
            return confidence_text + f"You're currently ${gap:.2f}/month short of your goal. " + \
                   f"Our AI recommendations would save ${potential:.2f}/month ({percent:.0f}% of what you need), " + \
                   f"putting you on track to reach your goal!"
        else:
            return confidence_text + f"You need to save ${required:.2f}/month but currently save ${current:.2f}/month. " + \
                   f"Our AI recommendations could save ${potential:.2f}/month, getting you closer to your goal!"
    
    
    def get_timeline_data(self):
        """Get daily spending for timeline charts"""
        daily = self.df[self.df['type'] == 'debit'].groupby(self.df['date'].dt.date)['amount'].sum().abs()
        
        return [
            {
                'date': str(date),
                'amount': float(amount)
            }
            for date, amount in daily.items()
        ]
    
    def get_category_trends(self):
        """Get spending trends by category over time"""
        df_debit = self.df[self.df['type'] == 'debit'].copy()
        df_debit['month'] = df_debit['date'].dt.to_period('M')
        
        monthly = df_debit.groupby(['month', 'category'])['amount'].sum().abs().reset_index()
        monthly['month'] = monthly['month'].astype(str)
        
        return monthly.to_dict('records')