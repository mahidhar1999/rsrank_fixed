import { useState, useEffect } from 'react'
import { portfolioAPI, paymentsAPI } from '../api/client'
import { useAuth } from '../context/AuthContext'
import PaywallGate from '../components/PaywallGate'
import Topbar from '../components/Topbar'
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'

export default function Portfolio() {
  const { isPro, user } = useAuth()
  const [preview, setPreview] = useState(null)
  const [holdings, setHoldings] = useState(null)
  const [perf, setPerf] = useState(null)
  const [loading, setLoading] = useState(true)
  const [paying, setPaying] = useState(false)

  useEffect(() => {
    if (isPro) {
      setLoading(true)
      portfolioAPI.current()
        .then(setHoldings)
        .finally(() => setLoading(false))

      portfolioAPI.performance()
        .then(setPerf)
    } else {
      portfolioAPI.preview()
        .then(setPreview)
        .finally(() => setLoading(false))
    }
  }, [isPro])

  const handleUpgrade = async (plan = 'pro') => {
    if (!user) { window.location.href = '/login'; return }
    setPaying(true)
    try {
      const order = await paymentsAPI.createOrder(plan)
      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: 'RSRank',
        description: 'Pro Subscription - Rs499/month',
        order_id: order.order_id,
        handler: async (response) => {
          await paymentsAPI.verify({ ...response, plan })
          window.location.reload()
        },
        prefill: { email: user.email },
        theme: { color: '#1D9E75' },
      }
      const rzp = new window.Razorpay(options)
      rzp.open()
    } catch (e) {
      alert('Payment failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setPaying(false)
    }
  }

  return (
    <div className="main-content">
      <Topbar title="Model Portfolio" />
      <div className="page-body">

        {perf && (
          <div className="metrics-row">
            <div className="metric-card">
              <div className="metric-label">Portfolio Since 2024</div>
              <div className="metric-val pos">{perf.ytd_portfolio >= 0 ? '+' : ''}{perf.ytd_portfolio?.toFixed(1)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Nifty 500 Since 2024</div>
              <div className="metric-val">{perf.ytd_nifty >= 0 ? '+' : ''}{perf.ytd_nifty?.toFixed(1)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Alpha</div>
              <div className="metric-val" style={{ color: 'var(--blue)' }}>
                {perf.ytd_alpha >= 0 ? '+' : ''}{perf.ytd_alpha?.toFixed(1)}%
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Holdings</div>
              <div className="metric-val">50</div>
              <div className="metric-change" style={{ color: 'var(--txt3)' }}>Equal weight 2% each</div>
            </div>
          </div>
        )}
        {
          <PaywallGate preview={<PerformancePlaceholder />}>
            {perf && (
              <div className="card">
                <div className="card-head">
                  <div className="card-title">Portfolio vs Nifty 500 - Monthly Returns</div>
                </div>
                <div className="card-body">
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={perf.monthly_returns?.map(m => ({
                      month: m.month.slice(5),
                      Portfolio: parseFloat(m.portfolio_return.toFixed(2)),
                      'Nifty 500': parseFloat(m.nifty_return.toFixed(2)),
                    }))}>
                      <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v}%`} />
                      <Tooltip formatter={(v, n) => [`${v}%`, n]} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line type="monotone" dataKey="Portfolio" stroke="#1D9E75" strokeWidth={2} dot={{ r: 3 }} />
                      <Line type="monotone" dataKey="Nifty 500" stroke="#185FA5" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="4 4" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </PaywallGate>}

        <PaywallGate
          preview={preview && <PreviewHoldings preview={preview} />}
        >
          {holdings && (
            <div className="card">
              <div className="card-head">
                <div>
                  <div className="card-title">Current Holdings - {holdings.trade_date}</div>
                  <div className="card-sub">Top 50 Nifty 500 members by RS Combined - Equal weight {holdings.weight_per_stock}%</div>
                </div>
                <span className="pill pill-green">{holdings.holdings?.length} stocks</span>
              </div>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr><th>#</th><th>Symbol</th><th>Sector</th><th>RS Score</th><th>Pct</th><th>Close</th><th>Weight</th></tr>
                  </thead>
                  <tbody>
                    {holdings.holdings?.map(h => (
                      <tr key={h.symbol}>
                        <td style={{ color: 'var(--txt3)', fontSize: 11 }}>{h.rank}</td>
                        <td><span className="mono" style={{ fontWeight: 500 }}>{h.symbol}</span></td>
                        <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{h.sector || '-'}</td>
                        <td><span className="mono pos">{h.rs_combined?.toFixed(3)}</span></td>
                        <td><span className="pill pill-green">{h.pct_combined?.toFixed(0)}</span></td>
                        <td className="mono" style={{ fontSize: 11 }}>Rs{h.close?.toLocaleString('en-IN') || '-'}</td>
                        <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{h.weight_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </PaywallGate>

      </div >
    </div >
  )
}

function PerformancePlaceholder() {
  return (
    <div className="card" style={{ height: 200, background: 'var(--bg1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ fontSize: 12, color: 'var(--txt3)' }}>Performance chart</span>
    </div>
  )
}

function PreviewHoldings({ preview }) {
  return (
    <div className="card">
      <div className="card-head"><div className="card-title">Top 5 Nifty 500 Holdings Preview</div></div>
      <div className="table-scroll">
        <table className="data-table">
          <thead><tr><th>#</th><th>Symbol</th><th>RS Pct</th></tr></thead>
          <tbody>
            {preview.preview?.map((p, i) => (
              <tr key={p.symbol}>
                <td style={{ color: 'var(--txt3)' }}>{i + 1}</td>
                <td><span className="mono" style={{ fontWeight: 500 }}>{p.symbol}</span></td>
                <td><span className="pill pill-green">{p.pct_combined?.toFixed(0)}</span></td>
              </tr>
            ))}
            <tr>
              <td colSpan={3} style={{ textAlign: 'center', color: 'var(--txt3)', fontSize: 11, padding: 12 }}>
                + {(preview.total_holdings || 50) - 5} more holdings - sign up to view all
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
