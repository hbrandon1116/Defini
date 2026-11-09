import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useLocation } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetMeQueryKey,
  getListUsersQueryKey,
  useGetMe,
  useLogin,
  useLogout,
} from "@/api-client";
import type { AuthUser, LoginRequest } from "@/api-client";

type AuthValue = {
  user: AuthUser | null;
  isLoading: boolean;
  error: boolean;
  login: (credentials: LoginRequest) => void;
  logout: () => void;
  isLoggingIn: boolean;
  isLoggingOut: boolean;
  loginError: string | null;
  clearLoginError: () => void;
};
const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [, setLocation] = useLocation();
  const cache = useQueryClient();
  const me = useGetMe({
    request: { credentials: "include" },
    query: { queryKey: getGetMeQueryKey(), retry: false },
  });
  const signIn = useLogin({
    request: { credentials: "include" },
    mutation: {
      onSuccess: (user) => {
        cache.setQueryData(getGetMeQueryKey(), user);
        void cache.removeQueries({ queryKey: getListUsersQueryKey() });
        setLocation("/");
      },
    },
  });
  const signOut = useLogout({
    request: { credentials: "include" },
    mutation: {
      onSuccess: () => {
        cache.setQueryData(getGetMeQueryKey(), null);
        void cache.removeQueries({ queryKey: getListUsersQueryKey() });
        setLocation("/login");
      },
    },
  });
  const loginError = useMemo(() => {
    if (!signIn.isError) return null;
    return "No pudimos validar tus datos. Revisa el usuario y la contraseña.";
  }, [signIn.isError]);
  const value: AuthValue = {
    user: me.data ?? null,
    isLoading: me.isLoading,
    error: me.isError,
    login: (credentials) => signIn.mutate({ data: credentials }),
    logout: () => signOut.mutate(),
    isLoggingIn: signIn.isPending,
    isLoggingOut: signOut.isPending,
    loginError,
    clearLoginError: () => signIn.reset(),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return value;
}
