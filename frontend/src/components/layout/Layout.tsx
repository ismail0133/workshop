import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  ArrowLeftRight,
  Bot,
  BrainCircuit,
  ChevronRight,
  CreditCard,
  Layers3,
  LayoutDashboard,
  LogOut,
  Menu,
  Server,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import { useAuth, canBank } from "../../features/auth/AuthProvider";
import { useHealth } from "../../hooks/useData";
import { Badge, Button } from "../ui";
export const navigation = [
  { path: "/", label: "Overview", icon: LayoutDashboard },
  { path: "/accounts", label: "Accounts", icon: CreditCard, bank: true },
  { path: "/payments", label: "Payments", icon: ArrowLeftRight, bank: true },
  { path: "/transactions", label: "Transactions", icon: Activity, bank: true },
  { path: "/infrastructure", label: "Infrastructure", icon: Server },
  {
    path: "/security",
    label: "Security Center",
    icon: ShieldCheck,
    future: true,
  },
  {
    path: "/ai-detection",
    label: "AI Detection",
    icon: BrainCircuit,
    future: true,
  },
  {
    path: "/recovery",
    label: "Autonomous Recovery",
    icon: Workflow,
    future: true,
  },
  { path: "/assistant", label: "AI Assistant", icon: Bot, future: true },
];
export function Layout() {
  const { user, logout } = useAuth();
  const health = useHealth("payment");
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const title =
    navigation.find((n) => n.path === location.pathname)?.label || "Détail";
  return (
    <div className="shell">
      <a className="skip-link" href="#content">
        Aller au contenu
      </a>
      {open && (
        <button
          className="nav-backdrop"
          aria-label="Fermer la navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <NavLink className="brand" to="/">
          <span className="brand-icon">
            <Layers3 size={23} />
          </span>
          <span>
            RESILIENCE<small>ALPHA / CONTROL CENTER</small>
          </span>
        </NavLink>
        <Button
          className="mobile-close"
          variant="ghost"
          aria-label="Fermer"
          onClick={() => setOpen(false)}
        >
          <X />
        </Button>
        <div className="workspace">
          <span className="workspace-icon">RA</span>
          <div>
            Workshop EPSI<small>Laboratoire bancaire</small>
          </div>
          <Badge tone="cyan">DEV</Badge>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Navigation principale">
          {navigation.map((item, i) => (
            <div key={item.path}>
              {i === 4 && (
                <div className="nav-label second">RESILIENCE PLATFORM</div>
              )}
              <NavLink
                end={item.path === "/"}
                to={item.path}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `nav-item ${isActive ? "active" : ""}`
                }
              >
                <item.icon size={19} />
                <span>{item.label}</span>
                {item.future && <span className="nav-dot" />}
                {item.bank && !canBank(user) && (
                  <span className="nav-lock">—</span>
                )}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="env-indicator">
            <span className="dot" />
            ENVIRONNEMENT FICTIF
          </div>
          <p>Aucune donnée bancaire réelle.</p>
          <div className="version">
            PLATFORM <span>v0.2.0</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <Button
              className="mobile-menu"
              variant="ghost"
              aria-label="Ouvrir la navigation"
              onClick={() => setOpen(true)}
            >
              <Menu />
            </Button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <div className="topbar-right">
            <Badge tone={health.data?.status === "ok" ? "good" : "neutral"}>
              {health.isPending
                ? "Vérification…"
                : health.data?.status === "ok"
                  ? "API connectée"
                  : "API indisponible"}
            </Badge>
            <span className="topbar-divider" />
            <details className="user-menu">
              <summary>
                <span className="avatar">
                  {user?.email.slice(0, 2).toUpperCase()}
                </span>
                <span className="user-text">
                  {user?.email.split("@")[0]}
                  <small>{user?.role}</small>
                </span>
              </summary>
              <div className="user-dropdown">
                <p>{user?.email}</p>
                <Button variant="ghost" onClick={logout}>
                  <LogOut size={17} />
                  Se déconnecter
                </Button>
              </div>
            </details>
          </div>
        </header>
        <main id="content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="page-footer">
          <span>
            RESILIENCE-ALPHA <span className="muted">/</span> BANKING CONTROL
            CENTER
          </span>
          <span>Fictional banking · Phase 02</span>
        </footer>
      </div>
    </div>
  );
}
