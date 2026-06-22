import { Link, useLocation } from 'react-router-dom'
import './AppShell.less'

export default function AppShell({ eyebrow, title, description, actions, children }) {
  const location = useLocation()
  const isConsole = location.pathname === '/'

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-copy">
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          {description && <p>{description}</p>}
        </div>
        <div className="header-actions">
          <nav className="app-nav" aria-label="主导航">
            <Link to="/" className={isConsole ? 'active' : ''}>
              流水线
            </Link>
            <Link to="/agents" className={location.pathname.startsWith('/agent') ? 'active' : ''}>
              独立工作台
            </Link>
          </nav>
          {actions}
        </div>
      </header>
      {children}
    </div>
  )
}
