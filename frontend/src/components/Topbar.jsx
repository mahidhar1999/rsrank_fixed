import { useState, useEffect } from 'react'
import { marketAPI } from '../api/client'

export default function Topbar({ title }) {
  const [date, setDate] = useState('')

  useEffect(() => {
    marketAPI.latestDate().then(d => setDate(d.latest_date || '')).catch(() => {})
  }, [])

  return (
    <header style={{
      background: 'var(--bg0)', borderBottom: '0.5px solid var(--border)',
      padding: '0 24px', height: 52,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      position: 'sticky', top: 0, zIndex: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 15, fontWeight: 600 }}>{title}</span>
        {date && (
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--txt3)',
            background: 'var(--bg2)', padding: '3px 10px', borderRadius: 4,
            border: '0.5px solid var(--border)',
          }}>
            {date}
          </span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--txt2)' }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
        NSE Data Live
      </div>
    </header>
  )
}
