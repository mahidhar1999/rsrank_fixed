import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV = [
  { to: '/', label: 'Overview', icon: GridIcon },
  { to: '/heatmap', label: 'RS Heatmap', icon: HeatIcon },
  { to: '/sectors', label: 'Sector Rotation', icon: PieIcon },
  { to: '/portfolio', label: 'Model Portfolio', icon: ChartIcon },
  { to: '/acceleration', label: 'Acceleration', icon: TrendIcon },
  { to: '/leadership', label: 'Leadership', icon: StarIcon },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <aside style={{
      background: 'var(--bg0)', borderRight: '0.5px solid var(--border)',
      display: 'flex', flexDirection: 'column', padding: '0',
      height: '100vh', position: 'sticky', top: 0,
    }}>
      <div style={{ padding: '20px', borderBottom: '0.5px solid var(--border)' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: '20px', fontWeight: 700, letterSpacing: '-0.5px' }}>
          RS<span style={{ color: 'var(--green)' }}>Rank</span>
        </div>
        <div style={{ fontSize: '10px', color: 'var(--txt3)', letterSpacing: '1.2px', textTransform: 'uppercase', marginTop: '2px' }}>
          Relative Strength Engine
        </div>
      </div>

      <nav style={{ flex: 1, padding: '8px 0', overflowY: 'auto' }}>
        <div style={{ fontSize: '10px', letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--txt3)', padding: '14px 20px 6px' }}>
          Core
        </div>
        {NAV.slice(0, 4).map(item => <NavItem key={item.to} {...item} />)}

        <div style={{ fontSize: '10px', letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--txt3)', padding: '14px 20px 6px' }}>
          Analysis
        </div>
        {NAV.slice(4).map(item => <NavItem key={item.to} {...item} />)}
      </nav>

      <div style={{ borderTop: '0.5px solid var(--border)', padding: '14px 16px' }}>
        {user ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                background: 'var(--green-light)', color: 'var(--green-dark)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 600, fontSize: '12px',
              }}>
                {(user.full_name || user.email)[0].toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize: '12px', fontWeight: 500 }}>{user.full_name || user.email.split('@')[0]}</div>
                <div style={{ fontSize: '10px', color: 'var(--txt3)' }}>
                  MVP access
                </div>
              </div>
            </div>
            <button className="btn" style={{ width: '100%', justifyContent: 'center', fontSize: '12px' }} onClick={logout}>
              Sign out
            </button>
          </>
        ) : (
          <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => navigate('/login')}>
            Sign in
          </button>
        )}
      </div>
    </aside>
  )
}

function NavItem({ to, label, icon: Icon }) {
  return (
    <NavLink to={to} end={to === '/'} style={({ isActive }) => ({
      display: 'flex', alignItems: 'center', gap: '10px',
      padding: '9px 20px', fontSize: '13px', color: 'var(--txt2)',
      borderLeft: `2px solid ${isActive ? 'var(--green)' : 'transparent'}`,
      background: 'transparent', transition: 'all 0.12s',
      fontWeight: isActive ? 500 : 400,
      ...(isActive ? { color: 'var(--txt)', background: 'var(--bg1)' } : {}),
    })}>
      <Icon size={15} />
      {label}
    </NavLink>
  )
}

function GridIcon({ size }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
}
function HeatIcon({ size }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="1" y="1" width="3" height="3" rx="0.5"/><rect x="6" y="1" width="3" height="3" rx="0.5"/><rect x="11" y="1" width="4" height="3" rx="0.5"/><rect x="1" y="6" width="3" height="4" rx="0.5"/><rect x="6" y="6" width="9" height="4" rx="0.5"/><rect x="1" y="12" width="14" height="3" rx="0.5"/></svg>
}
function PieIcon({ size }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor"><path d="M8 1v7l5 3A7 7 0 108 1z" opacity="0.4"/><path d="M8 1A7 7 0 013 13l5-5V1z"/></svg>
}
function ChartIcon({ size }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 12L5 8l3 2 3-4 3 2"/><rect x="1" y="1" width="14" height="14" rx="2"/></svg>
}
function TrendIcon({ size }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 14L8 4l2 4 2-3 2 2"/></svg>
}
function StarIcon({ size }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor"><path d="M8 1l2 4h4l-3 2.5 1 4.5L8 10l-4 2 1-4.5L2 5h4z"/></svg>
}
