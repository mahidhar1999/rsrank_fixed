// ── Acceleration Page ─────────────────────────────────────────────
import { useState, useEffect } from 'react'
import { accelAPI, leaderAPI } from '../api/client'
import Topbar from '../components/Topbar'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export function Acceleration() {
  const [data, setData] = useState(null)
  const [loading, setLoad] = useState(true)

  useEffect(() => {
    accelAPI.data({ limit: 20 }).then(setData).finally(() => setLoad(false))
  }, [])

  const emerging = data?.emerging || []
  const fading = data?.fading || []

  return (
    <div className="main-content">
      <Topbar title="RS Acceleration" />
      <div className="page-body">

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* Emerging leaders */}
          <div className="card">
            <div className="card-head">
              <div><div className="card-title">Emerging Leaders</div><div className="card-sub">ΔRS improving most in 10 days</div></div>
              <span className="pill pill-green">{emerging.length}</span>
            </div>
            {loading ? <div className="loading-center"><div className="spinner" /></div> : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead><tr><th>Symbol</th><th>Sector</th><th>RS Score</th><th>10D Delta</th></tr></thead>
                  <tbody>
                    {emerging.map(s => (
                      <tr key={s.symbol}>
                        <td><span className="mono" style={{ fontWeight: 500 }}>{s.symbol}</span></td>
                        <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{s.sector || '—'}</td>
                        <td><span className="mono">{s.rs_combined?.toFixed(3)}</span></td>
                        <td><span className="mono pos">+{s.delta_combined?.toFixed(4)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Fading */}
          <div className="card">
            <div className="card-head">
              <div><div className="card-title">Fading Momentum</div><div className="card-sub">ΔRS declining most in 10 days</div></div>
              <span className="pill pill-red">{fading.length}</span>
            </div>
            {loading ? <div className="loading-center"><div className="spinner" /></div> : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead><tr><th>Symbol</th><th>Sector</th><th>RS Score</th><th>10D Delta</th></tr></thead>
                  <tbody>
                    {fading.map(s => (
                      <tr key={s.symbol}>
                        <td><span className="mono" style={{ fontWeight: 500 }}>{s.symbol}</span></td>
                        <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{s.sector || '—'}</td>
                        <td><span className="mono">{s.rs_combined?.toFixed(3)}</span></td>
                        <td><span className="mono neg">{s.delta_combined?.toFixed(4)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Bar chart of deltas */}
        <div className="card">
          <div className="card-head"><div className="card-title">Top 20 Movers — 10D RS Delta</div></div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                layout="vertical"
                data={[...emerging.slice(0, 10), ...fading.slice(0, 10)].map(s => ({
                  symbol: s.symbol,
                  delta: parseFloat((s.delta_combined || 0).toFixed(4)),
                }))}
              >
                <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(3)} />
                <YAxis type="category" dataKey="symbol" tick={{ fontSize: 10, fontFamily: 'DM Mono, monospace' }} width={80} />
                <Tooltip formatter={(v) => [v.toFixed(4), 'Δ RS']} />
                <Bar dataKey="delta" radius={[0, 3, 3, 0]}>
                  {[...emerging.slice(0, 10), ...fading.slice(0, 10)].map((s, i) => (
                    <Cell key={i} fill={(s.delta_combined || 0) >= 0 ? '#1D9E75' : '#E24B4A'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
    </div>
  )
}


// ── Leadership Page ───────────────────────────────────────────────
export function Leadership() {
  const [data, setData] = useState(null)
  const [loading, setLoad] = useState(true)
  const [minStab, setMin] = useState(60)

  useEffect(() => {
    leaderAPI.data({ min_stability: minStab, limit: 50 }).then(setData).finally(() => setLoad(false))
  }, [minStab])

  return (
    <div className="main-content">
      <Topbar title="Leadership Stability" />
      <div className="page-body">

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 12, color: 'var(--txt2)' }}>Min stability:</span>
          <div className="tabs">
            {[50, 60, 70, 80].map(v => (
              <button key={v} className={`tab-item ${minStab === v ? 'active' : ''}`} onClick={() => setMin(v)}>
                {v}%+
              </button>
            ))}
          </div>
          <span style={{ fontSize: 11, color: 'var(--txt3)' }}>
            % of last 30 trading days in top RS percentile
          </span>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Structural Leaders</div>
              <div className="card-sub">Stocks that consistently stay in the top RS tier</div>
            </div>
            <span className="pill pill-blue">{data?.stocks?.length || 0} stocks</span>
          </div>
          {loading ? <div className="loading-center"><div className="spinner" /></div> : (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr><th>#</th><th>Symbol</th><th>Sector</th><th>Stability</th><th>RS Score</th><th>Pct</th></tr>
                </thead>
                <tbody>
                  {data?.stocks?.map((s, i) => (
                    <tr key={s.symbol}>
                      <td style={{ color: 'var(--txt3)', fontSize: 11 }}>{i + 1}</td>
                      <td><span className="mono" style={{ fontWeight: 500 }}>{s.symbol}</span></td>
                      <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{s.sector || '—'}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ width: 50, height: 4, background: 'var(--bg2)', borderRadius: 2, overflow: 'hidden' }}>
                            <div style={{ width: `${s.stability_score || 0}%`, height: '100%', background: 'var(--green)', borderRadius: 2 }} />
                          </div>
                          <span className="mono" style={{ fontSize: 11 }}>{s.stability_score?.toFixed(0)}%</span>
                        </div>
                      </td>
                      <td><span className="mono pos">{s.rs_combined?.toFixed(3)}</span></td>
                      <td><span className="pill pill-green">{s.pct_combined?.toFixed(0)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
