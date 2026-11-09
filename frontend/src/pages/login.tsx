import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { Box, LockKeyhole, UserRound } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";

export default function Login() {
  const { login, isLoggingIn, loginError, clearLoginError, user, isLoading } = useAuth();
  const [, navigate] = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  useEffect(() => { if (user) navigate(user.role === "admin" ? "/usuarios" : "/inventario"); }, [user, navigate]);
  return (
    <main className="login-page">
      <section className="login-side">
        <div className="login-content">
          <div className="login-mark" aria-hidden="true"><Box size={38} strokeWidth={1.8} /></div>
          <h1>Bienvenido</h1>
          <p className="login-intro">Defini — Gestión de Inventario</p>
          {loginError && <div className="form-alert" role="alert" data-testid="status-login-error">{loginError}</div>}
          <form className="login-form" onSubmit={(event) => { event.preventDefault(); login({ username: username.trim(), password }); }}>
            <label htmlFor="username">Usuario</label>
            <div className="field-with-icon"><UserRound size={17} /><input id="username" name="username" autoComplete="username" placeholder="Ej: admin" value={username} onChange={(event) => { setUsername(event.target.value); if (loginError) clearLoginError(); }} required data-testid="input-username" /></div>
            <label htmlFor="password">Contraseña</label>
            <div className="field-with-icon"><LockKeyhole size={17} /><input id="password" name="password" type="password" autoComplete="current-password" placeholder="••••••••" value={password} onChange={(event) => { setPassword(event.target.value); if (loginError) clearLoginError(); }} required data-testid="input-password" /></div>
            <button className="primary-button login-submit" type="submit" disabled={isLoggingIn || isLoading} data-testid="button-login">
              {isLoggingIn ? <><span className="button-spinner" /> Validando acceso</> : "Ingresar al Sistema"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
