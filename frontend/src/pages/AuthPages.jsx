import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { paymentsAPI } from '../api/client'

function AuthCard({ children, title, subtitle }) {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: 'var(--bg1)', padding: 24,
    }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 700 }}>
            RS<span style={{ color: 'var(--green)' }}>Rank</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--txt3)', letterSpacing: '1.2px', textTransform: 'uppercase', marginTop: 4 }}>
            Relative Strength Engine
          </div>
        </div>
        <div className="card" style={{ padding: 28 }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 18, marginBottom: 4 }}>{title}</h2>
          <p style={{ fontSize: 12, color: 'var(--txt2)', marginBottom: 24 }}>{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  )
}

function Field({ label, type = 'text', value, onChange, placeholder }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: 'block', fontSize: 12, color: 'var(--txt2)', marginBottom: 6 }}>{label}</label>
      <input
        type={type} value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '9px 12px', fontSize: 13,
          background: 'var(--bg1)', border: '0.5px solid var(--border2)',
          borderRadius: 'var(--radius-sm)', color: 'var(--txt)', outline: 'none',
        }}
        onFocus={e => e.target.style.borderColor = 'var(--green)'}
        onBlur={e => e.target.style.borderColor = 'var(--border2)'}
      />
    </div>
  )
}

export function Login() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const { login }               = useAuth()
  const navigate                = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Welcome back" subtitle="Sign in to your RSRank account">
      <form onSubmit={submit}>
        <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com" />
        <Field label="Password" type="password" value={password} onChange={setPassword} placeholder="••••••••" />
        {error && <div style={{ fontSize: 12, color: 'var(--red)', marginBottom: 14 }}>{error}</div>}
        <button className="btn btn-primary" type="submit"
          style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
      <p style={{ fontSize: 12, color: 'var(--txt3)', textAlign: 'center', marginTop: 16 }}>
        Don't have an account?{' '}
        <Link to="/register" style={{ color: 'var(--green)' }}>Create one</Link>
      </p>
    </AuthCard>
  )
}

export function Register() {
  const [name, setName]         = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const { register }            = useAuth()
  const navigate                = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await register(email, password, name)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Create account" subtitle="Start analyzing market momentum for free">
      <form onSubmit={submit}>
        <Field label="Full name" value={name} onChange={setName} placeholder="Your name" />
        <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com" />
        <Field label="Password" type="password" value={password} onChange={setPassword} placeholder="Min 8 characters" />
        {error && <div style={{ fontSize: 12, color: 'var(--red)', marginBottom: 14 }}>{error}</div>}
        <button className="btn btn-primary" type="submit"
          style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
          {loading ? 'Creating account...' : 'Create account'}
        </button>
      </form>
      <p style={{ fontSize: 12, color: 'var(--txt3)', textAlign: 'center', marginTop: 16 }}>
        Already have an account?{' '}
        <Link to="/login" style={{ color: 'var(--green)' }}>Sign in</Link>
      </p>
    </AuthCard>
  )
}

// ── Razorpay checkout hook — reusable across pages ────────────────
export function useRazorpay() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [paying, setPaying] = useState(false)

  const openCheckout = async (plan = 'pro') => {
    if (!user) { navigate('/login'); return }

    // Check Razorpay script loaded
    if (!window.Razorpay) {
      alert('Payment system loading — please try again in a moment.')
      return
    }

    setPaying(true)
    try {
      const order = await paymentsAPI.createOrder(plan)

      const options = {
        key:         order.key_id,
        amount:      order.amount,
        currency:    order.currency,
        name:        'RSRank',
        description: 'Pro Subscription — ₹499/month',
        order_id:    order.order_id,
        handler: async (response) => {
          try {
            await paymentsAPI.verify({ ...response, plan })
            alert('Payment successful! Welcome to Pro.')
            window.location.href = '/portfolio'
          } catch (err) {
            alert('Payment verification failed — contact support.')
          }
        },
        prefill: {
          email: user.email,
          name:  user.full_name || '',
        },
        theme: { color: '#1D9E75' },
        modal: {
          ondismiss: () => setPaying(false),
        },
      }

      const rzp = new window.Razorpay(options)
      rzp.on('payment.failed', (resp) => {
        alert('Payment failed: ' + (resp.error?.description || 'Unknown error'))
        setPaying(false)
      })
      rzp.open()

    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Could not create order'
      alert('Payment error: ' + msg)
      setPaying(false)
    }
  }

  return { openCheckout, paying }
}

export function Pricing() {
  const { user, isPro } = useAuth()
  const navigate        = useNavigate()
  const { openCheckout, paying } = useRazorpay()

  const features = {
    free: [
      'RS Heatmap (Top 100)',
      'Sector Rotation',
      'Acceleration Chart',
      'Leadership Stability',
      'Top 5 Portfolio Preview',
    ],
    pro: [
      'Everything in Free',
      'Full 50-stock Model Portfolio',
      'Monthly Performance vs Nifty 500',
      'Rebalance History',
      'Portfolio Alpha Analytics',
      'Early access to new features',
    ],
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg1)', padding: '48px 24px' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 700, marginBottom: 8 }}>
            Simple pricing
          </div>
          <p style={{ fontSize: 14, color: 'var(--txt2)' }}>
            Start free. Upgrade when the numbers speak for themselves.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Free */}
          <div className="card" style={{ padding: 28 }}>
            <div style={{ fontSize: 13, color: 'var(--txt3)', marginBottom: 6 }}>Free</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 32, fontWeight: 700, marginBottom: 20 }}>₹0</div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28 }}>
              {features.free.map(f => (
                <li key={f} style={{ display: 'flex', gap: 8, fontSize: 13 }}>
                  <span style={{ color: 'var(--green)' }}>✓</span> {f}
                </li>
              ))}
            </ul>
            <button className="btn" style={{ width: '100%', justifyContent: 'center' }}
              onClick={() => navigate(user ? '/' : '/register')}>
              {user ? 'Current plan' : 'Get started free'}
            </button>
          </div>

          {/* Pro */}
          <div className="card" style={{ padding: 28, border: '1.5px solid var(--green)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <div style={{ fontSize: 13, color: 'var(--txt3)' }}>Pro</div>
              <span className="pill pill-green">Most popular</span>
            </div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 32, fontWeight: 700, marginBottom: 4 }}>
              ₹499
            </div>
            <div style={{ fontSize: 12, color: 'var(--txt3)', marginBottom: 20 }}>per month</div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28 }}>
              {features.pro.map(f => (
                <li key={f} style={{ display: 'flex', gap: 8, fontSize: 13 }}>
                  <span style={{ color: 'var(--green)' }}>✦</span> {f}
                </li>
              ))}
            </ul>
            {isPro ? (
              <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled>
                Active plan ✓
              </button>
            ) : user ? (
              <button
                className="btn btn-razorpay"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => openCheckout('pro')}
                disabled={paying}
              >
                {paying ? 'Opening checkout...' : 'Subscribe — ₹499/mo'}
              </button>
            ) : (
              <button className="btn btn-razorpay" style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => navigate('/register')}>
                Get started
              </button>
            )}
          </div>
        </div>

        <p style={{ textAlign: 'center', fontSize: 11, color: 'var(--txt3)', marginTop: 24 }}>
          Payments secured by Razorpay · Cancel anytime · No hidden fees
        </p>
      </div>
    </div>
  )
}
