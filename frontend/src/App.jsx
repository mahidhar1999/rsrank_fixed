import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Sidebar from './components/Sidebar'
import Overview from './pages/Overview'
import Heatmap  from './pages/Heatmap'
import Sectors  from './pages/Sectors'
import Portfolio from './pages/Portfolio'
import { Acceleration, Leadership } from './pages/AnalysisPages'
import { Login, Register, Pricing } from './pages/AuthPages'
import './index.css'

function DashboardLayout({ children }) {
  return (
    <div className="app-shell">
      <Sidebar />
      {children}
    </div>
  )
}

function AppRoutes() {
  const { loading } = useAuth()
  if (loading) return null

  return (
    <Routes>
      <Route path="/login"    element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/pricing"  element={<Pricing />} />

      <Route path="/" element={<DashboardLayout><Overview /></DashboardLayout>} />
      <Route path="/heatmap"      element={<DashboardLayout><Heatmap /></DashboardLayout>} />
      <Route path="/sectors"      element={<DashboardLayout><Sectors /></DashboardLayout>} />
      <Route path="/portfolio"    element={<DashboardLayout><Portfolio /></DashboardLayout>} />
      <Route path="/acceleration" element={<DashboardLayout><Acceleration /></DashboardLayout>} />
      <Route path="/leadership"   element={<DashboardLayout><Leadership /></DashboardLayout>} />

      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
