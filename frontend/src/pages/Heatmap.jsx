import { useState, useEffect } from 'react'
import { stocksAPI } from '../api/client'
import Topbar from '../components/Topbar'

const BUCKET_CLASS = {
  h5: 'hm-h5', h4: 'hm-h4', h3: 'hm-h3', h2: 'hm-h2', h1: 'hm-h1',
  n:  'hm-n',
  l1: 'hm-l1', l2: 'hm-l2', l3: 'hm-l3', l4: 'hm-l4', l5: 'hm-l5',
}

const LEGEND = [
  { bucket: 'l5', label: '< 5' },
  { bucket: 'l4', label: '5-10' },
  { bucket: 'l3', label: '10-20' },
  { bucket: 'l2', label: '20-30' },
  { bucket: 'l1', label: '30-45' },
  { bucket: 'n',  label: '45-55' },
  { bucket: 'h1', label: '55-65' },
  { bucket: 'h2', label: '65-75' },
  { bucket: 'h3', label: '75-85' },
  { bucket: 'h4', label: '85-95' },
  { bucket: 'h5', label: '95-100' },
]

export default function Heatmap() {
  const [data, setData]         = useState(null)
  const [limit, setLimit]       = useState(100)
  const [loading, setLoading]   = useState(true)
  const [tooltip, setTooltip]   = useState(null)

  useEffect(() => {
    setLoading(true)
    stocksAPI.heatmap({ limit }).then(setData).finally(() => setLoading(false))
  }, [limit])

  return (
    <div className="main-content">
      <Topbar title="RS Heatmap" />
      <div className="page-body">

        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="tabs">
            {[50, 100, 200, 500].map(n => (
              <button key={n} className={`tab-item ${limit === n ? 'active' : ''}`} onClick={() => setLimit(n)}>
                Top {n}
              </button>
            ))}
          </div>
          <span style={{ fontSize: 11, color: 'var(--txt3)' }}>
            {data?.stocks?.length || 0} stocks · sorted by RS percentile
          </span>
        </div>

        {/* Heatmap grid */}
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">RS Percentile Heatmap — vs Nifty 50</div>
              <div className="card-sub">Hover for details · Green = strong RS · Red = weak RS</div>
            </div>
          </div>
          <div className="card-body">
            {loading ? (
              <div className="loading-center"><div className="spinner" /></div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${Math.ceil(Math.sqrt(data?.stocks?.length || 100))}, 1fr)`,
                gap: 3,
              }}>
                {data?.stocks?.map(s => (
                  <div
                    key={s.symbol}
                    className={`hm-cell ${BUCKET_CLASS[s.color_bucket] || 'hm-n'}`}
                    title={`${s.symbol}\nRS: ${s.rs_combined?.toFixed(3)}\nPct: ${s.pct_combined?.toFixed(0)}`}
                    onMouseEnter={e => setTooltip({ s, x: e.clientX, y: e.clientY })}
                    onMouseLeave={() => setTooltip(null)}
                  >
                    {s.symbol.slice(0, 4)}
                  </div>
                ))}
              </div>
            )}

            {/* Legend */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 16, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 10, color: 'var(--txt3)', marginRight: 4 }}>Weak</span>
              {LEGEND.map(l => (
                <div key={l.bucket} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <div className={`hm-cell ${BUCKET_CLASS[l.bucket]}`} style={{ width: 18, height: 12, borderRadius: 2, fontSize: 0 }} />
                  <span style={{ fontSize: 9, color: 'var(--txt3)' }}>{l.label}</span>
                </div>
              ))}
              <span style={{ fontSize: 10, color: 'var(--txt3)', marginLeft: 4 }}>Strong</span>
            </div>
          </div>
        </div>

        {/* Tooltip */}
        {tooltip && (
          <div style={{
            position: 'fixed', left: tooltip.x + 12, top: tooltip.y - 60,
            background: 'var(--bg0)', border: '0.5px solid var(--border2)',
            borderRadius: 8, padding: '10px 14px', fontSize: 12,
            boxShadow: 'var(--shadow-md)', zIndex: 999, pointerEvents: 'none',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, marginBottom: 4 }}>{tooltip.s.symbol}</div>
            <div style={{ color: 'var(--txt2)' }}>{tooltip.s.sector || '—'}</div>
            <div className="mono" style={{ color: 'var(--green)', marginTop: 4 }}>
              RS {tooltip.s.rs_combined?.toFixed(3)} · {tooltip.s.pct_combined?.toFixed(0)}th pct
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
