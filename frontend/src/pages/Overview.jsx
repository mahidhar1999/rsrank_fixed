import { useState, useEffect } from 'react'
import { marketAPI, stocksAPI, sectorsAPI } from '../api/client'
import Topbar from '../components/Topbar'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts'

export default function Overview() {
  const [summary, setSummary]   = useState(null)
  const [rankings, setRankings] = useState(null)
  const [sectors,  setSectors]  = useState(null)
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    Promise.all([
      marketAPI.summary(),
      stocksAPI.rankings({ limit: 20 }),
      sectorsAPI.rotation(),
    ]).then(([s, r, sec]) => {
      setSummary(s); setRankings(r); setSectors(sec)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingPage />

  return (
    <div className="main-content">
      <Topbar title="Market Overview" />
      <div className="page-body">

        {/* Metric cards */}
        <div className="metrics-row">
          <MetricCard label="Nifty 50" val={summary?.nifty50_close?.toLocaleString('en-IN') || '—'}
            change={summary?.nifty50_change_pct} suffix="%" />
          <MetricCard label="Universe" val={summary?.universe_size || '—'} change={null} note="Top 750 liquid" />
          <MetricCard label="RS Leaders" val={summary?.leaders || 0} color="var(--green)" note="RS > 1.2" />
          <MetricCard label="RS Laggards" val={summary?.laggards || 0} color="var(--red)" note="RS < 0.8" />
          <MetricCard label="Top Sector" val={summary?.top_sector?.name || '—'} change={null}
            note={summary?.top_sector ? `RS ${summary.top_sector.rs.toFixed(2)}` : ''} />
        </div>

        <div className="two-col">
          {/* Stock Rankings Table */}
          <div className="card">
            <div className="card-head">
              <div>
                <div className="card-title">Top 20 Stocks — RS Combined</div>
                <div className="card-sub">65D × 0.75 + 125D × 0.25 vs Nifty 50</div>
              </div>
            </div>
            <div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th><th>Symbol</th><th>Sector</th>
                    <th>RS Score</th><th>Mkt %ile</th><th>Stability</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings?.stocks?.map((s, i) => (
                    <tr key={s.symbol}>
                      <td style={{ color: 'var(--txt3)', fontSize: 11 }}>{i + 1}</td>
                      <td><span className="mono" style={{ fontWeight: 500 }}>{s.symbol}</span></td>
                      <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{s.sector || '—'}</td>
                      <td>
                        <span className="mono" style={{ color: s.rs_combined >= 1 ? 'var(--green)' : 'var(--red)' }}>
                          {s.rs_combined?.toFixed(3) || '—'}
                        </span>
                      </td>
                      <td>
                        <span className={`pill ${s.pct_combined >= 80 ? 'pill-green' : s.pct_combined >= 50 ? 'pill-blue' : 'pill-red'}`}>
                          {s.pct_combined?.toFixed(0) || '—'}
                        </span>
                      </td>
                      <td style={{ fontSize: 11 }}>{s.stability_score?.toFixed(0) || '—'}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Sector RS sidebar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="card">
              <div className="card-head"><div className="card-title">Sector RS vs Nifty 50</div></div>
              <div className="card-body">
                {sectors?.sectors?.slice(0, 8).map(s => (
                  <SectorBar key={s.index_name} sector={s} />
                ))}
              </div>
            </div>
            <div className="card">
              <div className="card-head">
                <div><div className="card-title">Market Breadth</div></div>
              </div>
              <div className="card-body">
                <BreadthChart leaders={summary?.leaders} laggards={summary?.laggards} neutral={summary?.neutral} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, val, change, color, note, suffix = '' }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-val" style={color ? { color } : {}}>
        {typeof val === 'number' ? val.toLocaleString() : val}
      </div>
      <div className="metric-change">
        {change != null ? (
          <span className={change >= 0 ? 'pos' : 'neg'}>
            {change >= 0 ? '▲' : '▼'} {Math.abs(change).toFixed(2)}{suffix}
          </span>
        ) : (
          <span style={{ color: 'var(--txt3)' }}>{note}</span>
        )}
      </div>
    </div>
  )
}

function SectorBar({ sector }) {
  const rs   = sector.rs_65d || 0
  const pct  = Math.max(0, Math.min(100, (rs / 1.5) * 100))
  const color = rs >= 1.1 ? 'var(--green)' : rs >= 0.95 ? 'var(--blue)' : 'var(--red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--txt2)', width: 120, flexShrink: 0 }}>
        {sector.index_name.replace('Nifty ', '')}
      </span>
      <div style={{ flex: 1, background: 'var(--bg2)', borderRadius: 2, height: 6, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.8s ease' }} />
      </div>
      <span className="mono" style={{ fontSize: 11, width: 40, textAlign: 'right', color }}>
        {rs.toFixed(2)}
      </span>
    </div>
  )
}

function BreadthChart({ leaders = 0, laggards = 0, neutral = 0 }) {
  const total = leaders + laggards + neutral || 1
  const data = [
    { name: 'Leaders', value: leaders,  fill: '#1D9E75' },
    { name: 'Neutral', value: neutral,  fill: '#9c9a92' },
    { name: 'Laggards',value: laggards, fill: '#E24B4A' },
  ]
  return (
    <div>
      {data.map(d => (
        <div key={d.name} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
            <span style={{ color: 'var(--txt2)' }}>{d.name}</span>
            <span className="mono">{d.value} <span style={{ color: 'var(--txt3)' }}>({((d.value / total) * 100).toFixed(0)}%)</span></span>
          </div>
          <div style={{ background: 'var(--bg2)', borderRadius: 3, height: 8, overflow: 'hidden' }}>
            <div style={{ width: `${(d.value / total) * 100}%`, height: '100%', background: d.fill, borderRadius: 3 }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function LoadingPage() {
  return (
    <div className="main-content">
      <Topbar title="Market Overview" />
      <div className="loading-center">
        <div className="spinner" />
        Loading market data...
      </div>
    </div>
  )
}
