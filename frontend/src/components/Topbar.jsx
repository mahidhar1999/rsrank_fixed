import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { marketAPI } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Topbar({ title }) {
  const [date, setDate]   = useState('')
  const { user }          = useAuth()
  const navigate          = useNavigate()

  useEffect(() => {
    marketAPI.latestDate().then(d => setDate(d.latest_date || '')).catch(() => {})
  }, [])

  return (
    <header style={{
      background:'var(--bg0)', borderBottom:'0.5px solid var(--border)',
      padding:'0 16px', height:52,
      display:'flex', alignItems:'center', justifyContent:'space-between',
      position:'sticky', top:0, zIndex:10,
    }}>
      <div style={{display:'flex',alignItems:'center',gap:10,minWidth:0}}>
        <span style={{fontFamily:'var(--font-display)',fontSize:15,fontWeight:600,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
          {title}
        </span>
        {date && (
          <span className="topbar-date" style={{
            fontFamily:'var(--font-mono)',fontSize:10,color:'var(--txt3)',
            background:'var(--bg2)',padding:'2px 8px',borderRadius:4,
            border:'0.5px solid var(--border)',whiteSpace:'nowrap',flexShrink:0,
          }}>
            {date}
          </span>
        )}
      </div>

      <div style={{display:'flex',alignItems:'center',gap:8,flexShrink:0}}>
        {/* Live indicator */}
        <div style={{display:'flex',alignItems:'center',gap:5,fontSize:11,color:'var(--txt2)'}}>
          <span style={{width:6,height:6,borderRadius:'50%',background:'var(--green)',display:'inline-block',flexShrink:0}}/>
          <span className="topbar-date">NSE Live</span>
        </div>

        {/* User avatar (mobile — desktop shows in sidebar) */}
        <div className="topbar-avatar" style={{}}>
          {user ? (
            <div
              onClick={() => navigate('/pricing')}
              style={{
                width:30,height:30,borderRadius:'50%',
                background:'var(--green-light)',color:'var(--green-dark)',
                display:'flex',alignItems:'center',justifyContent:'center',
                fontWeight:600,fontSize:12,cursor:'pointer',
              }}
            >
              {(user.full_name||user.email)[0].toUpperCase()}
            </div>
          ) : (
            <button className="btn btn-primary" style={{padding:'5px 12px',fontSize:12}}
              onClick={() => navigate('/login')}>
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
