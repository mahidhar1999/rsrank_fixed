import { useState, useEffect } from 'react'
import { marketAPI } from '../api/client'

export default function Topbar({ title }) {
  const [date, setDate] = useState('')

  useEffect(() => {
    marketAPI.latestDate()
      .then(d => setDate(d.latest_date || ''))
      .catch(() => { })
  }, [])

  return (
    <header style={{
      background: 'var(--bg0)', borderBottom: '0.5px solid var(--border)',
      padding: '0 16px', height: 52,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      position: 'sticky', top: 0, zIndex: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 15, fontWeight: 600 }}>
          {title}
        </span>

        {date && (
          <span style={{
            fontSize: 10,
            color: 'var(--txt3)',
            background: 'var(--bg2)',
            padding: '2px 8px',
            borderRadius: 4,
          }}>
            {date}
          </span>
        )}
      </div>

      {/* Live indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11 }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: 'var(--green)'
        }} />
        NSE Live
      </div>
    </header>
  )
}