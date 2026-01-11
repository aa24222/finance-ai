import React, { useState, useEffect, useCallback } from 'react';
import { PieChart, Pie, Cell, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './App.css';

const API_BASE = 'http://localhost:5000/api';

// ========== API Helper ==========
const api = {
  get: async (endpoint) => {
    const res = await fetch(`${API_BASE}${endpoint}`);
    return res.json();
  },
  post: async (endpoint, data) => {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data ?? {})
    });
    return res.json();
  },
  upload: async (endpoint, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST', body: formData });
    return res.json();
  }
};

// ========== Format Helpers ==========
const formatCurrency = (amount) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(Number(amount || 0));

const formatCurrencyDecimal = (amount) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(amount || 0));

// ========== Color Palette ==========
const COLORS = ['#0d9488', '#f59e0b', '#6366f1', '#ec4899', '#84cc16', '#f97316', '#8b5cf6', '#14b8a6'];

// ========== Components ==========

// Data Source Banner
function DataSourceBanner({ dataStatus, onReset }) {
  if (!dataStatus || dataStatus.data_source === 'demo') return null;

  return (
    <div className="data-banner">
      <span>
        📊 Using uploaded data: <strong>{dataStatus.file_name}</strong>
      </span>
      <button onClick={onReset} className="btn-small">Reset to Demo</button>
    </div>
  );
}

// File Upload Component
function FileUpload({ onUploadSuccess, dataStatus }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragOut = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) handleFile(files[0]);
  }, []);

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files.length > 0) handleFile(e.target.files[0]);
  };

  const handleFile = async (file) => {
    if (!file?.name?.toLowerCase().endsWith('.csv')) {
      setError('Please upload a CSV file');
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const result = await api.upload('/data/upload', file);
      if (result?.success) {
        onUploadSuccess?.();
      } else {
        setError(result?.error || 'Upload failed');
      }
    } catch {
      setError('Failed to upload file');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="upload-section">
      <div
        className={`upload-zone ${isDragging ? 'dragging' : ''} ${isUploading ? 'uploading' : ''}`}
        onDragEnter={handleDragIn}
        onDragLeave={handleDragOut}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".csv"
          onChange={handleFileInput}
          className="file-input"
          id="file-upload"
        />
        <label htmlFor="file-upload" className="upload-label">
          <span className="upload-icon">{isUploading ? '⏳' : '📁'}</span>
          <span className="upload-text">{isUploading ? 'Uploading...' : 'Drop CSV here or click to upload'}</span>
          <span className="upload-hint">
            {dataStatus?.data_source === 'demo' ? 'Currently using demo data' : `Using: ${dataStatus?.file_name}`}
          </span>
        </label>
      </div>
      {error && <div className="upload-error">{error}</div>}
    </div>
  );
}

// Summary Cards
function SummaryCards({ stats }) {
  if (!stats) return <div className="loading">Loading summary...</div>;

  const cards = [
    { label: 'Total Income', value: formatCurrency(stats.total_income), icon: '💰', color: 'green' },
    { label: 'Total Spending', value: formatCurrency(stats.total_spending), icon: '💸', color: 'red' },
    { label: 'Net Balance', value: formatCurrency(stats.net_balance), icon: '📊', color: Number(stats.net_balance) >= 0 ? 'green' : 'red' },
    { label: 'Monthly Avg', value: formatCurrency(stats.avg_monthly_spending), icon: '📅', color: 'blue' }
  ];

  return (
    <div className="summary-cards">
      {cards.map((card, i) => (
        <div key={i} className={`summary-card ${card.color}`}>
          <div className="card-icon">{card.icon}</div>
          <div className="card-content">
            <span className="card-label">{card.label}</span>
            <span className="card-value">{card.value}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// Category Breakdown Chart
function CategoryChart({ categories }) {
  if (!categories || categories.length === 0) return null;

  const data = categories.slice(0, 6).map((cat) => ({
    name: cat.category,
    value: Number(cat.amount || 0),
    percentage: Number(cat.percentage || 0)
  }));

  return (
    <div className="chart-card">
      <h3>Spending by Category</h3>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => formatCurrency(value)} />
          </PieChart>
        </ResponsiveContainer>

        <div className="chart-legend">
          {data.map((item, i) => (
            <div key={i} className="legend-item">
              <span className="legend-color" style={{ backgroundColor: COLORS[i] }}></span>
              <span className="legend-label">{item.name}</span>
              <span className="legend-value">{item.percentage.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Timeline Chart
function TimelineChart({ timeline }) {
  if (!timeline || timeline.length === 0) return null;

  // Aggregate by week for cleaner visualization
  const aggregated = timeline.reduce((acc, item) => {
    const d = new Date(item.date);
    if (Number.isNaN(d.getTime())) return acc;

    const weekStart = new Date(d);
    weekStart.setDate(d.getDate() - d.getDay());
    const key = weekStart.toISOString().split('T')[0];

    if (!acc[key]) acc[key] = { date: key, amount: 0 };
    acc[key].amount += Number(item.amount || 0);
    return acc;
  }, {});

  const data = Object.values(aggregated).slice(-12);

  return (
    <div className="chart-card wide">
      <h3>Spending Timeline</h3>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#0d9488" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="date"
            tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            stroke="#9ca3af"
            fontSize={12}
          />
          <YAxis tickFormatter={(val) => `$${val}`} stroke="#9ca3af" fontSize={12} />
          <Tooltip formatter={(value) => formatCurrency(value)} />
          <Area type="monotone" dataKey="amount" stroke="#0d9488" strokeWidth={2} fillOpacity={1} fill="url(#colorAmount)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Spending Habits Card
function SpendingHabits({ data }) {
  if (!data || !data.found) {
    return (
      <div className="insight-card">
        <h3>☕ Spending Habits</h3>
        <p className="no-data">No frequent spending habits detected</p>
      </div>
    );
  }

  const habit = data.data;

  return (
    <div className="insight-card">
      <h3>☕ Spending Habits</h3>

      <div className="habit-highlight">
        <span className="habit-merchant">{habit.habit_type}</span>
        <span className="habit-visits">{habit.num_visits} visits</span>
      </div>

      <div className="habit-stats">
        <div className="stat">
          <span className="stat-label">Total Spent</span>
          <span className="stat-value">{formatCurrencyDecimal(habit.total_spent)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Avg per Visit</span>
          <span className="stat-value">{formatCurrencyDecimal(habit.avg_per_visit)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Weekly Frequency</span>
          <span className="stat-value">{Number(habit.weekly_frequency || 0).toFixed(1)}x</span>
        </div>
      </div>

      <div className="savings-callout">
        <span className="savings-label">Potential Annual Savings</span>
        <span className="savings-value">{formatCurrency(habit.potential_savings)}</span>
        <span className="savings-hint">by cutting back 50%</span>
      </div>
    </div>
  );
}

// Subscriptions Card
function Subscriptions({ data }) {
  const subs = data?.data;

  if (!subs || !Array.isArray(subs.subscriptions) || subs.subscriptions.length === 0) {
    return (
      <div className="insight-card">
        <h3>💳 Subscriptions</h3>
        <p className="no-data">No recurring subscriptions detected</p>
      </div>
    );
  }

  const activeCount = Math.max(0, Number(subs.total_count || subs.subscriptions.length));
  const unusedCount = Math.max(0, Number(subs.unused_count || 0));
  const monthlyTotal = Number(subs.total_monthly_cost || 0);
  const unusedMonthlyWaste = Number(subs.unused_monthly_waste || 0);

  return (
    <div className="insight-card">
      <h3>💳 Subscriptions</h3>

      <div className="subs-summary">
        <div className="subs-stat">
          <span className="subs-count">{activeCount}</span>
          <span className="subs-label">Active</span>
        </div>

        <div className="subs-stat warning">
          <span className="subs-count">{unusedCount}</span>
          <span className="subs-label">Unused</span>
        </div>

        <div className="subs-stat">
          <span className="subs-count">{formatCurrency(monthlyTotal)}</span>
          <span className="subs-label">/month</span>
        </div>
      </div>

      <div className="subs-list">
        {subs.subscriptions.slice(0, 6).map((sub, i) => (
          <div key={i} className={`sub-item ${sub.likely_unused ? 'unused' : 'active'}`}>
            <div className="sub-left">
              <span className="sub-name">{sub.merchant}</span>
              {sub.last_charge_date && (
                <span className="sub-meta">Last:  {new Date(sub.last_charge_date).toLocaleDateString()}</span>
              )}
              {sub.trial_to_paid && <span className="sub-meta">Trial → Paid</span>}
            </div>

            <div className="sub-right">
              <span className="sub-amount">{formatCurrencyDecimal(sub.monthly_cost)}/mo</span>
              {sub.likely_unused && <span className="sub-badge">Review</span>}
            </div>
          </div>
        ))}
      </div>

      {unusedMonthlyWaste > 0 && (
        <div className="waste-callout">
          💡 Review unused subscriptions to save <strong>{formatCurrency(unusedMonthlyWaste * 12)}/year</strong>
        </div>
      )}
    </div>
  );
}

// Goal Tracker Card
function GoalTracker({ onCalculate, goalData }) {
  const [goalAmount, setGoalAmount] = useState(5000);
  const [goalMonths, setGoalMonths] = useState(12);
  const [isCalculating, setIsCalculating] = useState(false);

  const handleCalculate = async () => {
    setIsCalculating(true);
    await onCalculate?.(goalAmount, goalMonths);
    setIsCalculating(false);
  };

  const data = goalData?.data;

  const safeProjected = Number(data?.projected_total ?? 0);
  const safeGoal = Number(data?.goal_amount ?? 0);
  const progressPct =
    safeGoal > 0 ? Math.min(100, Math.max(0, (safeProjected / safeGoal) * 100)) : 0;

  const requiredMonthly = Number(data?.required_monthly_savings ?? 0);
  const currentMonthly = Number(data?.current_monthly_savings ?? 0);
  const monthlyGap = Number(data?.monthly_gap ?? (requiredMonthly - currentMonthly));
  const isNegativeTrend = safeProjected < 0;

  const verdictText = (() => {
    if (!data) return '';
    if (data.will_reach_goal) return '✅ On track to reach your goal!';
    if (isNegativeTrend) return `⚠️ Projected to lose ${formatCurrency(Math.abs(safeProjected))} over this timeframe`;
    return `⚠️ ${formatCurrency(data.shortfall)} short of goal`;
  })();

  return (
    <div className="insight-card goal-card">
      <h3>🎯 Goal Tracker</h3>

      <div className="goal-inputs">
        <div className="input-group">
          <label>Savings Goal</label>
          <div className="input-with-prefix">
            <span className="prefix">$</span>
            <input
              type="number"
              value={goalAmount}
              onChange={(e) => setGoalAmount(Number(e.target.value))}
              min="100"
              max="1000000"
            />
          </div>
        </div>

        <div className="input-group">
          <label>Timeframe</label>
          <div className="input-with-suffix">
            <input
              type="number"
              value={goalMonths}
              onChange={(e) => setGoalMonths(Number(e.target.value))}
              min="1"
              max="120"
            />
            <span className="suffix">months</span>
          </div>
        </div>

        <button className="btn-primary" onClick={handleCalculate} disabled={isCalculating}>
          {isCalculating ? 'Calculating...' : 'Calculate'}
        </button>
      </div>

      {data && (
        <div className="goal-results">
          <div className="goal-progress">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${progressPct}%`,
                  backgroundColor: data.will_reach_goal ? '#10b981' : '#f59e0b'
                }}
              ></div>
            </div>
            <div className="progress-labels">
              <span>{formatCurrency(safeProjected)}</span>
              <span>{formatCurrency(safeGoal)}</span>
            </div>
          </div>

          <div className={`goal-verdict ${data.will_reach_goal ? 'success' : 'warning'}`}>
            <span>{verdictText}</span>
          </div>

            <div className="goal-metrics">
        <div className="metric-row">
            <span className="metric-label">Required monthly savings</span>
            <span className="metric-value">{formatCurrencyDecimal(requiredMonthly)}</span>
        </div>

        <div className="metric-row">
            <span className="metric-label">Current monthly savings</span>
            <span className="metric-value">{formatCurrencyDecimal(currentMonthly)}</span>
        </div>

        <div className="metric-row gap">
            <span className="metric-label">Monthly gap</span>
            <span className="metric-value">{formatCurrencyDecimal(monthlyGap)}</span>
        </div>
        </div>


          {Array.isArray(data.recommendations) && data.recommendations.length > 0 && (
            <div className="recommendations">
              <h4>AI Recommendations</h4>
              {data.recommendations.map((rec, i) => (
                <div key={i} className="recommendation">
                  <span className="rec-action">{rec.action}</span>
                  <span className="rec-savings">+{formatCurrency(rec.monthly_savings)}/mo</span>
                </div>
              ))}
            </div>
          )}

          <div className="confidence-badge">
            ML Confidence: <strong>{data.confidence_level}</strong> ({data.confidence_percentage}%)
          </div>
        </div>
      )}
    </div>
  );
}

// Anomalies Card
function Anomalies({ data }) {
  if (!data || !data.found) {
    return (
      <div className="insight-card">
        <h3>🔍 Unusual Transactions</h3>
        <p className="no-data success">✓ No unusual transactions detected</p>
      </div>
    );
  }

  const anomalies = data.data;
  const anomalyCount = anomalies?.total_anomalies ?? anomalies?.anomalies?.length ?? 0;
  const safeTotal = Number.isFinite(Number(anomalies?.total_amount)) ? Number(anomalies.total_amount) : 0;
  const list = Array.isArray(anomalies?.anomalies) ? anomalies.anomalies : [];

  return (
    <div className="insight-card">
      <h3>🔍 Unusual Transactions</h3>

      <p className="anomaly-summary">
        Found <strong>{anomalyCount}</strong> unusual transactions totaling{' '}
        <strong>{formatCurrencyDecimal(safeTotal)}</strong>
      </p>

      <div className="anomaly-list">
        {list.slice(0, 4).map((a, i) => (
          <div key={i} className="anomaly-item">
            <div className="anomaly-main">
              <span className="anomaly-merchant">{a.merchant}</span>
              <span className="anomaly-amount">{formatCurrencyDecimal(Math.abs(Number(a.amount || 0)))}</span>
            </div>
            <div className="anomaly-reason">
              {Array.isArray(a.reasons) && a.reasons.length > 0 ? a.reasons[0] : 'unusual pattern detected by AI'}
            </div>
          </div>
        ))}
      </div>
      
    </div>
  );
}

// ========== Main App ==========
function App() {
  const [dataStatus, setDataStatus] = useState(null);
  const [summary, setSummary] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [spending, setSpending] = useState(null);
  const [subscriptions, setSubscriptions] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [goalData, setGoalData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAllData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [statusRes, summaryRes, timelineRes, spendingRes, subsRes, anomaliesRes] = await Promise.all([
        api.get('/data/status'),
        api.get('/summary'),
        api.get('/timeline'),
        api.get('/insights/spending'),
        api.get('/insights/subscriptions'),
        api.get('/insights/anomalies')
      ]);

      // Normalize success states
      if (summaryRes?.success === false) throw new Error(summaryRes?.error || 'Failed to load summary');

      setDataStatus(statusRes);
      setSummary(summaryRes);
      setTimeline(timelineRes);
      setSpending(spendingRes);
      setSubscriptions(subsRes);
      setAnomalies(anomaliesRes);
    } catch (err) {
      setError('Failed to connect to API. Make sure the backend is running on port 5000.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  const handleUploadSuccess = () => fetchAllData();

  const handleReset = async () => {
    await api.post('/data/reset');
    fetchAllData();
  };

  const handleGoalCalculate = async (amount, months) => {
    const result = await api.post('/insights/goal', { goal_amount: amount, goal_months: months });
    setGoalData(result);
  };

  if (error) {
    return (
      <div className="app">
        <div className="error-screen">
          <h1>⚠️ Connection Error</h1>
          <p>{error}</p>
          <button onClick={fetchAllData} className="btn-primary">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <DataSourceBanner dataStatus={dataStatus} onReset={handleReset} />

      <header className="header">
        <div className="header-content">
          <h1>🚀 Smart Financial Coach</h1>
          <p>AI-powered insights to transform your spending habits</p>
        </div>
        <FileUpload onUploadSuccess={handleUploadSuccess} dataStatus={dataStatus} />
      </header>

      {loading ? (
        <div className="loading-screen">
          <div className="spinner"></div>
          <p>Loading your financial data...</p>
        </div>
      ) : (
        <main className="dashboard">
          <SummaryCards stats={summary?.stats} />

          <div className="charts-row">
            <CategoryChart categories={summary?.categories} />
            <TimelineChart timeline={timeline?.data} />
          </div>

          <div className="insights-grid">
            <SpendingHabits data={spending} />
            <Subscriptions data={subscriptions} />
            <Anomalies data={anomalies} />
            <GoalTracker onCalculate={handleGoalCalculate} goalData={goalData} />
          </div>
        </main>
      )}

      <footer className="footer">
        <p>🔒 Your data stays local • No cloud storage • Privacy-first</p>
      </footer>
    </div>
  );
}

export default App;
