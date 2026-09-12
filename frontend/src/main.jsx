import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { AdminApp } from './admin/AdminApp.jsx'

// No router library is used anywhere in this app (ticket section 22).
// The admin dashboard is a second, independent root component that
// mounts instead of the public App only when the URL path is /admin --
// this is the only place that ever branches on the path, so the
// public bundle's own behavior is completely unaffected either way.
const isAdminRoute = window.location.pathname.startsWith('/admin')

createRoot(document.getElementById('root')).render(
  <StrictMode>{isAdminRoute ? <AdminApp /> : <App />}</StrictMode>,
)
