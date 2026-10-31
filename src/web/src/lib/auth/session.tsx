"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Spin } from "antd";
import { ApiError } from "@/lib/api/client";
import { authApi, type Role, type SessionUser } from "@/lib/api/auth";

type SessionContextValue = { user: SessionUser | null; loading: boolean; signIn: (user: SessionUser) => void; signOut: () => Promise<void>; refreshProfile: () => Promise<void> };
const SessionContext = createContext<SessionContextValue | null>(null);
const PUBLIC_PATHS = ["/", "/login", "/forgot-password"];

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();
  const lastActivity = useRef(0);

  const clearSession = useCallback(() => {
    sessionStorage.removeItem("qlttnn.account-slug");
    setUser(null);
  }, []);
  const signIn = useCallback((nextUser: SessionUser) => {
    sessionStorage.setItem("qlttnn.account-slug", nextUser.slug);
    setUser(nextUser);
  }, []);
  const refreshProfile = useCallback(async () => {
    const slug = sessionStorage.getItem("qlttnn.account-slug");
    if (!slug) { setUser(null); return; }
    const result = await authApi.profile(slug);
    setUser(result.user);
  }, []);
  const signOut = useCallback(async () => {
    try { if (user) await authApi.logout(); } finally { clearSession(); router.replace("/login"); }
  }, [clearSession, router, user]);

  useEffect(() => {
    let cancelled = false;
    const slug = sessionStorage.getItem("qlttnn.account-slug");
    if (!slug) { queueMicrotask(() => { if (!cancelled) setLoading(false); }); return () => { cancelled = true; }; }
    authApi.profile(slug).then((result) => { if (!cancelled) setUser(result.user); })
      .catch(() => { if (!cancelled) clearSession(); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [clearSession]);

  useEffect(() => {
    if (loading) return;
    if (!user && !PUBLIC_PATHS.includes(pathname)) router.replace("/login");
    if (user && ["/login", "/forgot-password"].includes(pathname)) router.replace(user.must_change_password ? "/password/change" : homeForRole(user.role));
    if (user?.must_change_password && pathname !== "/password/change") router.replace("/password/change");
  }, [loading, pathname, router, user]);

  useEffect(() => {
    if (!user) return;
    const recordActivity = () => {
      const now = Date.now();
      if (now - lastActivity.current < 45_000) return;
      lastActivity.current = now;
      authApi.activity().catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) { clearSession(); router.replace("/login"); }
      });
    };
    window.addEventListener("pointerdown", recordActivity, { passive: true });
    window.addEventListener("keydown", recordActivity);
    window.addEventListener("touchstart", recordActivity, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", recordActivity);
      window.removeEventListener("keydown", recordActivity);
      window.removeEventListener("touchstart", recordActivity);
    };
  }, [clearSession, router, user]);

  const value = useMemo(() => ({ user, loading, signIn, signOut, refreshProfile }), [user, loading, signIn, signOut, refreshProfile]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession phải nằm trong SessionProvider.");
  return context;
}

export function RequireSession({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user, loading } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (user && roles && !roles.includes(user.role)) router.replace(homeForRole(user.role));
  }, [roles, router, user]);
  if (loading || !user || (roles && !roles.includes(user.role))) return <Spin fullscreen description="Đang xác minh phiên đăng nhập..." />;
  return <>{children}</>;
}

export function homeForRole(role: Role) {
  if (role === "giao_vien") return "/teacher";
  if (role === "hoc_vien") return "/student";
  return "/admin/dashboard";
}
