"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Button, Result, Spin } from "antd";
import { ApiError } from "@/lib/api/client";
import { authApi, type Role, type SessionUser } from "@/lib/api/auth";

type SessionContextValue = {
  user: SessionUser | null;
  loading: boolean;
  restoreError: boolean;
  retrySession: () => void;
  signIn: (user: SessionUser, expiresAt: string) => void;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
};
const SessionContext = createContext<SessionContextValue | null>(null);
const PUBLIC_PATHS = ["/", "/login", "/forgot-password", "/courses", "/branches", "/programs", "/blog", "/contact"];

function isPublicPath(pathname: string) {
  return PUBLIC_PATHS.includes(pathname) || pathname.startsWith("/courses/") || pathname.startsWith("/blog/");
}

function keepLaterExpiry(current: string | null, next: string) {
  return current && Date.parse(current) > Date.parse(next) ? current : next;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState(false);
  const [restoreAttempt, setRestoreAttempt] = useState(0);
  const router = useRouter();
  const pathname = usePathname();
  const lastActivity = useRef(0);
  const authMutationVersion = useRef(0);

  const clearSession = useCallback(() => {
    authMutationVersion.current += 1;
    lastActivity.current = 0;
    sessionStorage.removeItem("qlttnn.account-slug");
    setUser(null);
    setExpiresAt(null);
    setRestoreError(false);
  }, []);
  const signIn = useCallback((nextUser: SessionUser, nextExpiresAt: string) => {
    authMutationVersion.current += 1;
    lastActivity.current = 0;
    sessionStorage.setItem("qlttnn.account-slug", nextUser.slug);
    setUser(nextUser);
    setExpiresAt(nextExpiresAt);
    setRestoreError(false);
    setLoading(false);
  }, []);
  const retrySession = useCallback(() => {
    setLoading(true);
    setRestoreError(false);
    setRestoreAttempt((attempt) => attempt + 1);
  }, []);
  const refreshProfile = useCallback(async () => {
    const version = authMutationVersion.current;
    const slug = sessionStorage.getItem("qlttnn.account-slug");
    if (!slug) { setUser(null); setExpiresAt(null); return; }
    const result = await authApi.profile(slug);
    if (version !== authMutationVersion.current) return;
    setUser(result.user);
    setExpiresAt((current) => keepLaterExpiry(current, result.expires_at));
  }, []);
  const signOut = useCallback(async () => {
    authMutationVersion.current += 1;
    try { await authApi.logout(); }
    catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) throw error;
    }
    clearSession();
    router.replace("/login");
  }, [clearSession, router]);

  useEffect(() => {
    let cancelled = false;
    const version = authMutationVersion.current;
    authApi.session().then((session) => {
      if (cancelled || version !== authMutationVersion.current) return;
      if (!session) { clearSession(); return; }
      const { user: sessionUser, expires_at } = session;
      sessionStorage.setItem("qlttnn.account-slug", sessionUser.slug);
      setUser(sessionUser);
      setExpiresAt((current) => keepLaterExpiry(current, expires_at));
      setRestoreError(false);
    }).catch((error: unknown) => {
      if (cancelled || version !== authMutationVersion.current) return;
      if (error instanceof ApiError && error.status === 401) clearSession();
      else setRestoreError(true);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [clearSession, restoreAttempt]);

  useEffect(() => {
    if (loading) return;
    if (!user && !restoreError && !isPublicPath(pathname)) router.replace("/login");
    if (user && ["/login", "/forgot-password"].includes(pathname)) router.replace(homeForRole(user.role));
  }, [loading, pathname, restoreError, router, user]);

  useEffect(() => {
    if (!user) return;
    const recordActivity = () => {
      const now = Date.now();
      if (now - lastActivity.current < 45_000) return;
      lastActivity.current = now;
      const version = authMutationVersion.current;
      authApi.activity().then(({ expires_at }) => {
        if (version !== authMutationVersion.current) return;
        setExpiresAt((current) => keepLaterExpiry(current, expires_at));
      }).catch((error: unknown) => {
        if (version !== authMutationVersion.current) return;
        if (error instanceof ApiError && error.status === 401) { clearSession(); router.replace("/login"); }
      });
    };
    window.addEventListener("pointerdown", recordActivity, { passive: true });
    window.addEventListener("keydown", recordActivity);
    window.addEventListener("touchstart", recordActivity, { passive: true });
    window.addEventListener("wheel", recordActivity, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", recordActivity);
      window.removeEventListener("keydown", recordActivity);
      window.removeEventListener("touchstart", recordActivity);
      window.removeEventListener("wheel", recordActivity);
    };
  }, [clearSession, router, user]);

  useEffect(() => {
    if (!user || !expiresAt) return;
    let cancelled = false;
    const version = authMutationVersion.current;
    const timer = window.setTimeout(() => {
      void authApi.session().then((session) => {
        if (cancelled || version !== authMutationVersion.current) return;
        if (!session) { clearSession(); router.replace("/login"); return; }
        const { user: sessionUser, expires_at } = session;
        setUser(sessionUser);
        setExpiresAt((current) => keepLaterExpiry(current, expires_at));
        setRestoreError(false);
      }).catch((error: unknown) => {
        if (cancelled || version !== authMutationVersion.current) return;
        if (error instanceof ApiError && error.status === 401) { clearSession(); router.replace("/login"); }
        else setRestoreError(true);
      });
    }, Math.max(5_000, Date.parse(expiresAt) - Date.now()));
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [clearSession, expiresAt, router, user]);

  const value = useMemo(() => ({ user, loading, restoreError, retrySession, signIn, signOut, refreshProfile }), [user, loading, restoreError, retrySession, signIn, signOut, refreshProfile]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession phải nằm trong SessionProvider.");
  return context;
}

export function RequireSession({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user, loading, restoreError, retrySession } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (user && roles && !roles.includes(user.role)) router.replace(homeForRole(user.role));
  }, [roles, router, user]);
  if (restoreError) return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <Result
        status="warning"
        title="Chưa xác minh được phiên đăng nhập"
        subTitle="API đang lỗi hoặc tạm thời không phản hồi. Cookie phiên được giữ nguyên; hãy thử kiểm tra lại."
        extra={<Button type="primary" onClick={retrySession}>Thử lại</Button>}
      />
    </main>
  );
  if (loading || !user || (roles && !roles.includes(user.role))) return <Spin fullscreen description="Đang xác minh phiên đăng nhập..." />;
  return <>{children}</>;
}

export function homeForRole(role: Role) {
  if (role === "giao_vien") return "/teacher";
  if (role === "hoc_vien") return "/student";
  return "/admin/dashboard";
}
