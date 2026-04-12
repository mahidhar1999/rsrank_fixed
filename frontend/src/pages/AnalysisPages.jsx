import { useEffect, useState } from 'react'
import { accelAPI, leaderAPI } from '../api/client'
import Topbar from '../components/Topbar'
import { BarChart, Bar, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export function Acceleration() {
  const [data, setData] = useState(null)
  const [loading, setLoad] = useState(true)
  const [view, setView] = useState('emerging')

  useEffect(() => {
    accelAPI.data({ limit: 20 }).then(setData).finally(() => setLoad(false))
  }, [])

  const emerging = data?.emerging || []
  const fading = data?.fading || []
  const visibleMovers = view === 'emerging' ? emerging : fading
  const strongestImprover = emerging[0]
  const sharpestFade = fading[0]
  const allMovers = [...emerging, ...fading]
  const avgAbsDelta = allMovers.length
    ? allMovers.reduce((sum, item) => sum + Math.abs(item.delta_combined || 0), 0) / allMovers.length
    : 0
  const chartData = [
    ...emerging.slice(0, 10).map(stock => toMomentumPoint(stock, 'up')),
    ...fading.slice(0, 10).map(stock => toMomentumPoint(stock, 'down')),
  ].sort((left, right) => right.delta - left.delta)
  const chartLimit = chartData.length
    ? Math.max(...chartData.map(item => Math.abs(item.delta))) * 1.15
    : 0.01

  return (
    <div className="main-content">
      <Topbar title="RS Acceleration" />
      <div className="page-body">
        {loading ? (
          <div className="loading-center">
            <div className="spinner" />
            Loading acceleration data...
          </div>
        ) : (
          <>
            {/*<div className="metrics-row">
              <MetricCard
                label="Top Improver"
                value={strongestImprover?.symbol || '-'}
                note={strongestImprover ? `${formatDelta(strongestImprover.delta_combined)} | ${strongestImprover.sector || 'Unknown sector'}` : 'No improving names'}
                color="var(--green)"
                mono
              />
              <MetricCard
                label="Sharpest Fade"
                value={sharpestFade?.symbol || '-'}
                note={sharpestFade ? `${formatDelta(sharpestFade.delta_combined)} | ${sharpestFade.sector || 'Unknown sector'}` : 'No fading names'}
                color="var(--red)"
                mono
              />
              <MetricCard
                label="Avg |Delta RS|"
                value={avgAbsDelta ? avgAbsDelta.toFixed(4) : '0.0000'}
                note="Mean 10-session shift"
                mono
              />
              <MetricCard
                label="Tracked Movers"
                value={`${allMovers.length}`}
                note={`${emerging.length} improving | ${fading.length} fading`}
              />
            </div>*/}

            {/*<div className="card">
              <div className="card-head">
                <div>
                  <div className="card-title">Top 20 Movers | 10D RS Delta</div>
                  <div className="card-sub">Improving names on the right, fading names on the left</div>
                </div>
              </div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={Math.max(280, chartData.length * 24)}>
                  <BarChart
                    layout="vertical"
                    data={chartData}
                    margin={{ top: 4, right: 8, bottom: 4, left: 4 }}
                    barCategoryGap={10}
                  >
                    <ReferenceLine x={0} stroke="var(--border2)" />
                    <XAxis
                      type="number"
                      domain={[-chartLimit, chartLimit]}
                      tick={{ fontSize: 10, fill: 'var(--txt3)' }}
                      tickFormatter={value => value.toFixed(3)}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="symbol"
                      width={80}
                      tick={{ fontSize: 10, fill: 'var(--txt)', fontFamily: 'DM Mono, monospace' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip cursor={{ fill: 'rgba(0, 0, 0, 0.04)' }} content={<MomentumTooltip />} />
                    <Bar dataKey="delta" radius={[3, 3, 3, 3]} barSize={16}>
                      {chartData.map(point => (
                        <Cell key={point.symbol} fill={point.tone === 'up' ? '#1D9E75' : '#E24B4A'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>*/}

            <div className="card">
              <div className="card-head">
                <div>
                  <div className="card-title">Ranked Movers</div>
                  <div className="card-sub">Switch between names gaining momentum and names losing traction</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <div className="tabs" style={{ width: 'auto', flex: '0 0 auto' }}>
                    <button className={`tab-item ${view === 'emerging' ? 'active' : ''}`} onClick={() => setView('emerging')}>
                      Emerging
                    </button>
                    <button className={`tab-item ${view === 'fading' ? 'active' : ''}`} onClick={() => setView('fading')}>
                      Fading
                    </button>
                  </div>
                  <span className={`pill ${view === 'emerging' ? 'pill-green' : 'pill-red'}`}>{visibleMovers.length} stocks</span>
                </div>
              </div>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr><th>#</th><th>Symbol</th><th>Sector</th><th>RS Score</th><th>10D Delta</th></tr>
                  </thead>
                  <tbody>
                    {visibleMovers.map((stock, index) => (
                      <tr key={stock.symbol}>
                        <td style={{ color: 'var(--txt3)', fontSize: 11 }}>{index + 1}</td>
                        <td><span className="mono" style={{ fontWeight: 500 }}>{stock.symbol}</span></td>
                        <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{stock.sector || '-'}</td>
                        <td><span className="mono">{formatRs(stock.rs_combined)}</span></td>
                        <td>
                          <span className={`mono ${view === 'emerging' ? 'pos' : 'neg'}`}>
                            {formatDelta(stock.delta_combined)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function MetricCard({ label, value, note, color, mono = false }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-val" style={{ color: color || 'inherit', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-display)' }}>
        {value}
      </div>
      <div className="metric-change">{note}</div>
    </div>
  )
}

function MomentumTooltip({ active, payload }) {
  if (!active || !payload?.length) return null

  const point = payload[0].payload

  return (
    <div style={{
      background: 'var(--bg0)',
      border: '0.5px solid var(--border2)',
      borderRadius: 8,
      padding: '10px 12px',
    }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{point.symbol}</div>
      <div style={{ fontSize: 11, color: 'var(--txt3)', marginTop: 2 }}>{point.sector || 'Unknown sector'}</div>
      <div style={{ fontSize: 12, color: point.tone === 'up' ? 'var(--green)' : 'var(--red)', marginTop: 6 }}>
        Delta RS {formatDelta(point.delta)}
      </div>
      <div style={{ fontSize: 11, color: 'var(--txt2)', marginTop: 2 }}>Current RS {formatRs(point.rs)}</div>
    </div>
  )
}

function toMomentumPoint(stock, tone) {
  return {
    symbol: stock.symbol,
    sector: stock.sector,
    rs: stock.rs_combined || 0,
    delta: parseFloat((stock.delta_combined || 0).toFixed(4)),
    tone,
  }
}

function formatDelta(value) {
  if (value == null) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(4)}`
}

function formatRs(value) {
  return value == null ? '-' : value.toFixed(3)
}

export function Leadership() {
  const [data, setData] = useState(null)
  const [loading, setLoad] = useState(true)
  const [minStab, setMin] = useState(80)

  useEffect(() => {
    let active = true
    setLoad(true)

    leaderAPI.data({ min_stability: minStab, limit: 200 })
      .then(response => {
        if (active) setData(response)
      })
      .finally(() => {
        if (active) setLoad(false)
      })

    return () => {
      active = false
    }
  }, [minStab])

  const resultCount = data?.stocks?.length || 0
  const totalMatches = data?.total ?? resultCount

  return (
    <div className="main-content">
      <Topbar title="Leadership Stability" />
      <div className="page-body">
        {/*<div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
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
        </div>*/}

        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Structural Leaders</div>
              <div className="card-sub">
                Stocks above the minimum stability filter, sorted by stability score and RS percentile
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span className="pill pill-gray">Min {minStab}%</span>
              <span className="pill pill-blue">
                {resultCount === totalMatches ? `${totalMatches} matches` : `Top ${resultCount} of ${totalMatches}`}
              </span>
            </div>
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
                      <td style={{ fontSize: 11, color: 'var(--txt3)' }}>{s.sector || '-'}</td>
                      <td><StabilityCell value={s.stability_score} /></td>
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

function StabilityCell({ value }) {
  if (value == null) {
    return <span className="hint">-</span>
  }

  const tone = value >= 80 ? 'pill-green' : value >= 70 ? 'pill-blue' : value >= 60 ? 'pill-amber' : 'pill-gray'
  const fill = value >= 80 ? 'var(--green)' : value >= 70 ? 'var(--blue)' : value >= 60 ? 'var(--amber)' : 'var(--txt3)'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 120 }}>
      <div style={{ flex: 1, height: 6, background: 'var(--bg2)', borderRadius: 999, overflow: 'hidden' }}>
        <div style={{ width: `${Math.max(0, Math.min(100, value))}%`, height: '100%', background: fill, borderRadius: 999 }} />
      </div>
      <span className={`pill ${tone}`}>{value.toFixed(0)}%</span>
    </div>
  )
}
