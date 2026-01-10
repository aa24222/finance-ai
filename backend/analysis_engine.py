import pandas as pd
import numpy as np
from datetime import datetime

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
        Forecasts whether user will reach savings goal and provides recommendations
        """
        # Calculate current financial situation
        days = (self.df['date'].max() - self.df['date'].min()).days
        months = max(1, days / 30.0)
        
        total_income = self.df[self.df['type'] == 'credit']['amount'].sum()
        total_spending = abs(self.df[self.df['type'] == 'debit']['amount'].sum())
        
        monthly_income = total_income / months
        monthly_spending = total_spending / months
        current_monthly_savings = monthly_income - monthly_spending
        
        # What's needed for goal
        required_monthly_savings = goal_amount / goal_months
        monthly_gap = required_monthly_savings - current_monthly_savings
        
        # Projection
        projected_total_savings = current_monthly_savings * goal_months
        will_reach_goal = projected_total_savings >= goal_amount
        shortfall = max(0, goal_amount - projected_total_savings)
        
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
        
        # Calculate success probability
        new_monthly_savings = current_monthly_savings + total_potential_savings
        success_probability = min(100, (new_monthly_savings / required_monthly_savings * 100)) if required_monthly_savings > 0 else 100
        
        # New projection with recommendations
        new_projected_total = new_monthly_savings * goal_months
        will_reach_with_changes = new_projected_total >= goal_amount
        
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
            'recommendations': recommendations,
            'total_potential_savings': float(total_potential_savings),
            'new_monthly_savings': float(new_monthly_savings),
            'new_projected_total': float(new_projected_total),
            'will_reach_with_changes': will_reach_with_changes,
            'success_probability': float(success_probability),
            'insight': self._generate_goal_insight(
                current_monthly_savings, 
                required_monthly_savings, 
                total_potential_savings,
                will_reach_goal,
                will_reach_with_changes
            )
        }
    
    def _generate_goal_insight(self, current, required, potential, reach_now, reach_with_changes):
        """Generate human-readable insight for goal"""
        gap = required - current
        
        if reach_now:
            return f"Great news! You're already on track to reach your goal. Keep it up!"
        elif reach_with_changes:
            percent = (potential / gap * 100) if gap > 0 else 0
            return f"You're currently ${gap:.2f}/month short of your goal. " + \
                   f"Our recommendations would save ${potential:.2f}/month ({percent:.0f}% of what you need), " + \
                   f"putting you on track to reach your goal!"
        else:
            return f"You need to save ${required:.2f}/month but currently save ${current:.2f}/month. " + \
                   f"Our recommendations could save ${potential:.2f}/month, getting you closer to your goal!"
    
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