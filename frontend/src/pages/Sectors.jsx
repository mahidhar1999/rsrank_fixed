// ── Sectors Page ──────────────────────────────────────────────────
import { useState, useEffect } from 'react'
import { sectorsAPI } from '../api/client'
import Topbar from '../components/Topbar'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'

export default function Sectors() {
  const [data, setData]     = useState(null)
  const [loading, setLoad]  = useState(true)

  useEffect(() => {
    sectorsAPI.rotation().then(setData).finally(() => setLoad(false))
  }, [])

  const sectors = data?.sectors || []

  return (
    <div className="main-content">
      <Topbar title="Sector Rotation" />
      <div className="page-body">

        <div className="two-col">
          {/* Sector RS table */}
          <div className="card">
            <div className="card-head">
              <div className="card-title">All Sectors vs Nifty 50</div>
            </div>
            {loading ? (
              <div className="loading-center"><div className="spinner" /></div>
            ) : (
              <div className="card-body" style={{ padding: 0 }}>
                <table className="data-table">
                  <thead>
                    <tr><th>Sector</th><th>RS 65D</th><th>RS 125D</th><th>Trend</th><th>Stocks</th></tr>
                  </thead>
                  <tbody>
                    {sectors.map(s => {
                      const rs = s.rs_65d || 0
                      const color = rs >= 1.1 ? 'var(--green)' : rs >= 0.95 ? 'var(--blue)' : 'var(--red)'
                      const arrow = s.trend === 'up' ? '▲' : s.trend === 'down' ? '▼' : '—'
                      const arrowCol = s.trend === 'up' ? 'var(--green)' : s.trend === 'down' ? 'var(--red)' : 'var(--txt3)'
                      return (
                        <tr key={s.index_name}>
                          <td style={{ fontSize: 12 }}>{s.index_name.replace('Nifty ', '')}</td>
                          <td><span className="mono" style={{ color }}>{s.rs_65d?.toFixed(3) || '—'}</span></td>
                          <td><span className="mono" style={{ color: 'var(--txt2)', fontSize: 11 }}>{s.rs_125d?.toFixed(3) || '—'}</span></td>
                          <td><span style={{ color: arrowCol, fontSize: 13 }}>{arrow}</span></td>
                          <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{s.stock_count}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Radar chart */}
          <div className="card">
            <div className="card-head"><div className="card-title">Rotation Radar</div></div>
            <div className="card-body">
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={sectors.slice(0, 10).map(s => ({
                  subject: s.index_name.replace('Nifty ', '').slice(0, 10),
                  rs: parseFloat(((s.rs_65d || 0) * 100).toFixed(1)),
                }))}>
                  <PolarGrid stroke="var(--border2)" />
                  <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: 'var(--txt3)' }} />
                  <Radar dataKey="rs" stroke="#1D9E75" fill="#1D9E75" fillOpacity={0.15} strokeWidth={1.5} />
                  <Tooltip formatter={(v) => [`${v}`, 'RS']} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
