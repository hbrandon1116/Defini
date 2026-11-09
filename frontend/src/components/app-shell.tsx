import { type ReactNode, useEffect } from "react";
import { Link, useLocation } from "wouter";
import { ArrowRight, LogOut, PackageSearch, ShieldCheck, Tags, UsersRound } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";

export function Protected({ children, adminOnly = false }: { children: ReactNode; adminOnly?: boolean }) {
  const { user, isLoading, error } = useAuth();
  const [, navigate] = useLocation();
  useEffect(() => {
    if (!isLoading && (!user || error)) navigate("/login");
    else if (!isLoading && adminOnly && user?.role !== "admin") navigate("/");
  }, [isLoading, user, error, adminOnly, navigate]);
  if (isLoading) return <div className="auth-loading"><div className="loading-mark" /><span>Validando sesión y permisos</span></div>;
  if (!user || error || (adminOnly && user.role !== "admin")) return null;
  return <>{children}</>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout, isLoggingOut } = useAuth();
  const [path] = useLocation();
  return (
    <div className="app-frame">
      <aside className="side-rail">
        <Link href="/" className="brand-lockup" data-testid="link-brand-home">
          <span className="brand-icon"><img src={`${import.meta.env.BASE_URL}images/logo.png`} alt="" /></span>
          <span><strong>defini</strong><small>GESTIÓN DE INVENTARIO</small></span>
        </Link>
         <div className="rail-caption">ESPACIO DE TRABAJO</div>
         <nav className="main-nav" aria-label="Navegación principal">
           {user?.role === "admin" && <Link href="/usuarios" className={`nav-link ${path === "/usuarios" ? "active" : ""}`} data-testid="link-usuarios">
             <UsersRound size={18} strokeWidth={1.8} /><span>Usuarios</span><ArrowRight className="nav-arrow" size={15} />
           </Link>}
           <Link href="/inventario" className={`nav-link ${path === "/inventario" ? "active" : ""}`} data-testid="link-inventario">
             <PackageSearch size={18} strokeWidth={1.8} /><span>Inventario</span><ArrowRight className="nav-arrow" size={15} />
           </Link>
           {user?.role === "admin" && <Link href="/tipos-producto" className={`nav-link ${path === "/tipos-producto" ? "active" : ""}`} data-testid="link-tipos-producto">
             <Tags size={18} strokeWidth={1.8} /><span>Tipos de producto</span><ArrowRight className="nav-arrow" size={15} />
           </Link>}
         </nav>
        <div className="rail-bottom">
          <div className="help-note"><div className="help-glyph"><ShieldCheck size={16} /></div><strong>Acceso bajo control.</strong><span>Roles claros para cada integrante.</span></div>
          <div className="profile">
            <div className="avatar">{user?.name?.slice(0, 1).toUpperCase() || "U"}</div>
            <div className="profile-copy"><strong>{user?.name}</strong><span>{user?.role === "admin" ? "Administrador" : "Empleado"}</span></div>
            <button className="icon-button logout-button" onClick={() => logout()} disabled={isLoggingOut} aria-label="Cerrar sesión" title="Cerrar sesión" data-testid="button-logout"><LogOut size={17} /></button>
          </div>
        </div>
      </aside>
      <main className="main-panel">
        <header className="mobile-header">
          <div className="mobile-header-top">
            <Link href="/" className="mobile-brand" data-testid="link-mobile-home"><span className="brand-icon"><img src={`${import.meta.env.BASE_URL}images/logo.png`} alt="" /></span><strong>defini</strong></Link>
            <nav className="mobile-nav-links" aria-label="Navegación principal">
              {user?.role === "admin" ? <>
                <Link href="/usuarios" className={`mobile-nav-link ${path === "/usuarios" ? "active" : ""}`} data-testid="link-mobile-usuarios"><UsersRound size={16} /> Usuarios</Link>
                <Link href="/inventario" className={`mobile-nav-link ${path === "/inventario" ? "active" : ""}`} data-testid="link-mobile-inventario"><PackageSearch size={16} /> Inventario</Link>
                <Link href="/tipos-producto" className={`mobile-nav-link ${path === "/tipos-producto" ? "active" : ""}`} data-testid="link-mobile-tipos-producto"><Tags size={16} /> Tipos</Link>
              </> : <Link href="/inventario" className={`mobile-nav-link ${path === "/inventario" ? "active" : ""}`} data-testid="link-mobile-inventario"><PackageSearch size={16} /> Inventario</Link>}
            </nav>
          </div>
        </header>
        <div className="mobile-context" aria-label="Cuenta y acceso">
          <div className="mobile-account-bar">
            <div className="mobile-profile">
              <div className="avatar">{user?.name?.slice(0, 1).toUpperCase() || "U"}</div>
              <div className="mobile-profile-copy"><strong>{user?.name}</strong><span>{user?.role === "admin" ? "Administrador" : "Empleado"}</span></div>
            </div>
            <button className="mobile-logout-button" onClick={() => logout()} disabled={isLoggingOut} data-testid="button-mobile-logout"><LogOut size={16} /><span>{isLoggingOut ? "Cerrando…" : "Cerrar sesión"}</span></button>
          </div>
          <div className="mobile-help-note"><ShieldCheck size={15} aria-hidden="true" /><span><strong>Acceso bajo control.</strong> Roles claros para cada integrante.</span></div>
        </div>
        <div className="page-wrap">{children}</div>
      </main>
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, action }: { eyebrow: string; title: string; subtitle: string; action?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action && <div className="heading-action">{action}</div>}</div>;
}

export function LoadingRows({ count = 5 }: { count?: number }) {
  return <div className="skeleton-list" aria-label="Cargando información">{Array.from({ length: count }, (_, i) => <div className="skeleton-row" key={i}><span /><span /><span /><span /></div>)}</div>;
}
