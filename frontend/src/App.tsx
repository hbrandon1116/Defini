import { type ReactNode, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ErrorBoundary } from "@/components/error-boundary";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppShell, Protected } from "@/components/app-shell";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import Login from "@/pages/login";
import Users from "@/pages/users";
import Inventory from "@/pages/inventory";
import ProductTypes from "@/pages/product-types";
import NotFound from "@/pages/not-found";
import { Route, Switch, useLocation, Router as WouterRouter } from "wouter";
import { KeyRound, LogOut } from "lucide-react";

const queryClient = new QueryClient();

function Home() {
  const { user, isLoading } = useAuth();
  const [, navigate] = useLocation();
  useEffect(() => {
    if (!isLoading) navigate(user ? (user.role === "admin" ? "/usuarios" : "/inventario") : "/login");
  }, [isLoading, user, navigate]);
  return <div className="auth-loading"><div className="loading-mark" /><span>Preparando tu espacio</span></div>;
}

function Restricted() {
  const { user, logout, isLoggingOut } = useAuth();
  return <AppShell><section className="restricted-panel">
    <div className="restricted-icon"><KeyRound size={25} /></div>
    <div className="eyebrow">ACCESO LIMITADO</div>
    <h1>Esta sección es para administradores.</h1>
    <p>Tu cuenta de empleado puede iniciar sesión, pero no tiene acceso a la administración de usuarios.</p>
    <div className="restricted-user"><span className="avatar">{user?.name?.slice(0, 1).toUpperCase()}</span><span><strong>{user?.name}</strong><small>Rol: Empleado</small></span></div>
    <button className="secondary-button" onClick={() => logout()} disabled={isLoggingOut} data-testid="button-restricted-logout"><LogOut size={16} /> Cerrar sesión</button>
  </section></AppShell>;
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function Router() {
  return <RoutedErrorBoundary><Switch>
    <Route path="/" component={Home} />
    <Route path="/login" component={Login} />
    <Route path="/usuarios">{() => <Protected adminOnly><AppShell><Users /></AppShell></Protected>}</Route>
    <Route path="/inventario">{() => <Protected><AppShell><Inventory /></AppShell></Protected>}</Route>
    <Route path="/tipos-producto">{() => <Protected adminOnly><AppShell><ProductTypes /></AppShell></Protected>}</Route>
    <Route path="/acceso-restringido">{() => <Protected><Restricted /></Protected>}</Route>
    <Route component={NotFound} />
  </Switch></RoutedErrorBoundary>;
}

function App() {
  return <QueryClientProvider client={queryClient}><TooltipProvider><WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}><AuthProvider><Router /></AuthProvider></WouterRouter><Toaster /></TooltipProvider></QueryClientProvider>;
}

export default App;
