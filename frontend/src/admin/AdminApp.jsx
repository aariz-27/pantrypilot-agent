import { useCallback, useEffect, useState } from 'react'
import { getSession, clearAdminSession } from '../services/adminApi.js'
import { AdminLogin } from './AdminLogin.jsx'
import { AdminLayout } from './AdminLayout.jsx'
import { AdminDashboard } from './AdminDashboard.jsx'
import { IngredientList } from './IngredientList.jsx'
import { IngredientEditor } from './IngredientEditor.jsx'
import { AuditLog } from './AuditLog.jsx'
import { GroceryProducts } from './GroceryProducts.jsx'
import './admin.css'

// Deliberately no router library (ticket section 22: "do not introduce
// another heavyweight frontend framework") -- a plain page/selection
// state, the same pattern App.jsx already uses for its own
// search/results/detail view switching.
const PAGES = {
  DASHBOARD: 'dashboard',
  INGREDIENTS: 'ingredients',
  PRICES: 'prices',
  AUDIT: 'audit',
  DATA_MAPPING: 'data_mapping',
}

export function AdminApp() {
  const [authState, setAuthState] = useState('checking') // 'checking' | 'authenticated' | 'unauthenticated'
  const [username, setUsername] = useState(null)
  const [page, setPage] = useState(PAGES.DASHBOARD)
  const [selectedIngredientId, setSelectedIngredientId] = useState(null)
  const [selectedIngredientSource, setSelectedIngredientSource] = useState(null)

  useEffect(() => {
    let cancelled = false
    getSession()
      .then((session) => {
        if (cancelled) return
        setUsername(session.username)
        setAuthState('authenticated')
      })
      .catch(() => {
        if (cancelled) return
        setAuthState('unauthenticated')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleLoginSuccess = useCallback((session) => {
    setUsername(session.username)
    setAuthState('authenticated')
  }, [])

  const handleLogout = useCallback(() => {
    clearAdminSession()
    setUsername(null)
    setAuthState('unauthenticated')
    setPage(PAGES.DASHBOARD)
    setSelectedIngredientId(null)
  }, [])

  const openIngredient = useCallback((canonicalId, source) => {
    setSelectedIngredientId(canonicalId)
    setSelectedIngredientSource(source ?? 'admin')
    setPage(PAGES.INGREDIENTS)
  }, [])

  const closeIngredientEditor = useCallback(() => {
    setSelectedIngredientId(null)
    setSelectedIngredientSource(null)
  }, [])

  if (authState === 'checking') {
    return (
      <div className="admin-boot-screen" role="status" aria-live="polite">
        Loading admin dashboard…
      </div>
    )
  }

  if (authState === 'unauthenticated') {
    return <AdminLogin onLoginSuccess={handleLoginSuccess} />
  }

  return (
    <AdminLayout username={username} page={page} onNavigate={setPage} onLogout={handleLogout} pages={PAGES}>
      {page === PAGES.DASHBOARD ? <AdminDashboard onOpenIngredient={openIngredient} /> : null}
      {page === PAGES.INGREDIENTS && selectedIngredientId ? (
        <IngredientEditor canonicalId={selectedIngredientId} source={selectedIngredientSource} onClose={closeIngredientEditor} />
      ) : null}
      {page === PAGES.INGREDIENTS && !selectedIngredientId ? <IngredientList onOpenIngredient={openIngredient} /> : null}
      {page === PAGES.PRICES ? (
        <IngredientList onOpenIngredient={openIngredient} priceFocusMode />
      ) : null}
      {page === PAGES.AUDIT ? <AuditLog /> : null}
      {page === PAGES.DATA_MAPPING ? <GroceryProducts /> : null}
    </AdminLayout>
  )
}
