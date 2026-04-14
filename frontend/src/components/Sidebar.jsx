import { useEffect, useState } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/*{ to: '/portfolio', label: 'Portfolio', shortLabel: 'Portfolio', Icon: ChartIcon },*/
const NAV = [
  { to: '/', label: 'Overview', shortLabel: 'Home', Icon: GridIcon },
  { to: '/heatmap', label: 'RS Heatmap', shortLabel: 'Heatmap', Icon: HeatIcon },
  { to: '/sectors', label: 'Sector Rotation', shortLabel: 'Sectors', Icon: PieIcon },
  { to: '/acceleration', label: 'Acceleration', shortLabel: 'Momentum', Icon: TrendIcon },
  { to: '/leadership', label: 'Leadership', shortLabel: 'Leaders', Icon: StarIcon },
]

// ── Desktop Sidebar ────────────────────────────────────────────
export default function Sidebar() {
  //const { user, logout, isPro } = useAuth()
  const navigate = useNavigate()

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className="sidebar-desktop"
        style={{
          background: 'var(--bg0)',
          borderRight: '0.5px solid var(--border)',
          flexDirection: 'column',

          height: '100vh',          // ✅ FIXED HEIGHT
          overflowY: 'auto',        // ✅ ENABLE SCROLL
          position: 'sticky',       // ✅ STICKY BACK (safe now)
          top: 0,

          flexShrink: 0,
        }}
      >
        {/* Logo */}
        <div style={{ padding: '20px', borderBottom: '0.5px solid var(--border)' }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700, letterSpacing: '-0.5px' }}>
            RS<span style={{ color: 'var(--green)' }}>Rank</span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--txt3)', letterSpacing: '1.2px', textTransform: 'uppercase', marginTop: 2 }}>
            Relative Strength Engine
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '8px 0' }}>
          <div style={{ fontSize: 10, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--txt3)', padding: '14px 20px 6px' }}>Core</div>
          {NAV.slice(0, 4).map(item => <DesktopNavItem key={item.to} {...item} />)}
          <div style={{ fontSize: 10, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--txt3)', padding: '14px 20px 6px' }}>Analysis</div>
          {NAV.slice(4).map(item => <DesktopNavItem key={item.to} {...item} />)}
        </nav>

        {/* Bottom */}
        {/*<div style={{ borderTop: '0.5px solid var(--border)', padding: '14px 16px' }}>
          {user ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--green-light)', color: 'var(--green-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: 12 }}>
                  {(user.full_name || user.email)[0].toUpperCase()}
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{user.full_name || user.email.split('@')[0]}</div>
                  <div style={{ fontSize: 10, color: 'var(--txt3)' }}>{isPro ? '✦ Pro' : 'Free plan'}</div>
                </div>
              </div>
              {!isPro && (
                <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', marginBottom: 6, fontSize: 12 }}
                  onClick={() => navigate('/pricing')}>
                  Upgrade to Pro
                </button>
              )}
              <button className="btn" style={{ width: '100%', justifyContent: 'center', fontSize: 12 }} onClick={logout}>
                Sign out
              </button>
            </>
          ) : (
            <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}
              onClick={() => navigate('/login')}>Sign in</button>
          )}
        </div>*/}
        <div style={{ borderTop: '0.5px solid var(--border)', padding: '14px 16px' }}>
          {/* Optional: keep empty or add branding/version */}
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <MobileBottomNav />
    </>
  )
}

// ── Desktop nav item ───────────────────────────────────────────
function DesktopNavItem({ to, label, Icon }) {
  return (
    <NavLink to={to} end={to === '/'} style={({ isActive }) => ({
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '9px 20px', fontSize: 13,
      color: isActive ? 'var(--txt)' : 'var(--txt2)',
      borderLeft: `2px solid ${isActive ? 'var(--green)' : 'transparent'}`,
      background: isActive ? 'var(--bg1)' : 'transparent',
      fontWeight: isActive ? 500 : 400,
      transition: 'all 0.12s', textDecoration: 'none',
    })}>
      <Icon size={15} />{label}
    </NavLink>
  )
}

// ── Mobile bottom navigation bar ──────────────────────────────
function MobileBottomNav() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [drawerOpen, setDrawer] = useState(false)

  // Lock background scroll without freezing the drawer itself on mobile browsers.
  useEffect(() => {
    const root = document.documentElement
    const body = document.body

    root.classList.toggle('mobile-nav-open', drawerOpen)
    body.classList.toggle('mobile-nav-open', drawerOpen)

    return () => {
      root.classList.remove('mobile-nav-open')
      body.classList.remove('mobile-nav-open')
    }
  }, [drawerOpen])

  // Bottom nav shows 4 primary items + "More" drawer
  const PRIMARY = NAV.slice(0, 4)

  return (
    <>
      <nav className="bottom-nav">
        {PRIMARY.map(({ to, shortLabel, Icon }) => {
          const active = to === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(to)
          return (
            <NavLink key={to} to={to} className={`bottom-nav-item ${active ? 'active' : ''}`}>
              <Icon size={20} />
              <span>{shortLabel}</span>
            </NavLink>
          )
        })}

        {/* More drawer trigger */}
        <button
          className={`bottom-nav-item ${drawerOpen ? 'active' : ''}`}
          onClick={() => setDrawer(true)}
          style={{ border: 'none' }}
        >
          <MoreIcon size={20} />
          <span>More</span>
        </button>
      </nav>

      {/* Slide-up drawer for remaining nav + account */}
      <div className={`drawer-overlay ${drawerOpen ? 'open' : ''}`} onClick={() => setDrawer(false)} />
      <MobileDrawer open={drawerOpen} onClose={() => setDrawer(false)} user={user} />
    </>
  )
}

// ── Mobile drawer (slides from bottom) ────────────────────────
function MobileDrawer({ open, onClose, user }) {
  const navigate = useNavigate()
  const { logout, isPro } = useAuth()

  const go = (path) => { navigate(path); onClose() }

  return (
    <div className={`mobile-drawer ${open ? 'open' : ''}`}>
      {/* Handle */}
      <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 4px' }}>
        <div style={{ width: 36, height: 4, borderRadius: 2, background: 'var(--bg3)' }} />
      </div>

      {/* Header */}
      <div style={{ padding: '8px 20px 12px', borderBottom: '0.5px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700 }}>
          RS<span style={{ color: 'var(--green)' }}>Rank</span>
        </div>
        <button onClick={onClose} style={{ border: 'none', background: 'none', fontSize: 20, color: 'var(--txt3)', cursor: 'pointer', padding: '4px 8px' }}>✕</button>
      </div>

      {/* More nav items */}
      <div style={{ padding: '8px 0' }}>
        <DrawerLabel label="Analysis" />
        {/*<DrawerItem label="Acceleration" Icon={TrendIcon} onClick={() => go('/acceleration')} />*/}
        <DrawerItem label="Leadership" Icon={StarIcon} onClick={() => go('/leadership')} />
        {/*<DrawerItem label="Pricing" Icon={DiamondIcon} onClick={() => go('/pricing')} />*/}
      </div>

      {/* Account section */}
      {/*<div style={{ borderTop: '0.5px solid var(--border)', padding: '8px 0' }}>
        <DrawerLabel label="Account" />
        {user ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px' }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--green-light)', color: 'var(--green-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: 14 }}>
                {(user.full_name || user.email)[0].toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{user.full_name || user.email.split('@')[0]}</div>
                <div style={{ fontSize: 11, color: 'var(--txt3)' }}>{user.email}</div>
              </div>
              <div style={{ marginLeft: 'auto' }}>
                <span className={`pill ${isPro ? 'pill-green' : 'pill-gray'}`}>{isPro ? 'Pro' : 'Free'}</span>
              </div>
            </div>
            {!isPro && (
              <div style={{ padding: '0 16px 8px' }}>
                <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}
                  onClick={() => go('/pricing')}>
                  Upgrade to Pro — ₹499/mo
                </button>
              </div>
            )}
            <DrawerItem label="Sign out" Icon={SignOutIcon} onClick={() => { logout(); onClose() }} danger />
          </>
        ) : (
          <div style={{ padding: '8px 16px' }}>
            <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}
              onClick={() => go('/login')}>Sign in</button>
          </div>
        )}
      </div>*/}
    </div>
  )
}

function DrawerLabel({ label }) {
  return (
    <div style={{ fontSize: 10, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--txt3)', padding: '6px 20px 4px', fontWeight: 500 }}>
      {label}
    </div>
  )
}

function DrawerItem({ label, Icon, onClick, danger }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 14,
      width: '100%', padding: '13px 20px',
      border: 'none', background: 'transparent',
      color: danger ? 'var(--red)' : 'var(--txt)',
      fontSize: 14, cursor: 'pointer', textAlign: 'left',
    }}>
      <Icon size={18} />{label}
    </button>
  )
}

/* ── Icons ──────────────────────────────────────────────────── */
function GridIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="6" rx="1" /><rect x="9" y="1" width="6" height="6" rx="1" /><rect x="1" y="9" width="6" height="6" rx="1" /><rect x="9" y="9" width="6" height="6" rx="1" /></svg> }
function HeatIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="1" y="1" width="3" height="3" rx="0.5" /><rect x="6" y="1" width="3" height="3" rx="0.5" /><rect x="11" y="1" width="4" height="3" rx="0.5" /><rect x="1" y="6" width="3" height="4" rx="0.5" /><rect x="6" y="6" width="9" height="4" rx="0.5" /><rect x="1" y="12" width="14" height="3" rx="0.5" /></svg> }
function PieIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor"><path d="M8 1v7l5 3A7 7 0 108 1z" opacity="0.4" /><path d="M8 1A7 7 0 013 13l5-5V1z" /></svg> }
function ChartIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 12L5 8l3 2 3-4 3 2" /><rect x="1" y="1" width="14" height="14" rx="2" /></svg> }
function TrendIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 14L8 4l2 4 2-3 2 2" /></svg> }
function StarIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor"><path d="M8 1l2 4h4l-3 2.5 1 4.5L8 10l-4 2 1-4.5L2 5h4z" /></svg> }
function MoreIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor"><circle cx="2.5" cy="8" r="1.5" /><circle cx="8" cy="8" r="1.5" /><circle cx="13.5" cy="8" r="1.5" /></svg> }
function DiamondIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M8 1l4 4-4 10-4-10z" /></svg> }
function SignOutIcon({ size }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M6 3H3v10h3M10 11l3-3-3-3M13 8H6" /></svg> }
