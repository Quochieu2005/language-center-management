"use client";

import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import AdminHeader from "./AdminHeader";
import AdminSidebar from "./AdminSidebar";
import AdminFooter from "./AdminFooter";
import { AdminThemeProvider } from "../theme/AdminThemeContext";
import { SiteScopeProvider, useSiteScope } from "@/lib/auth/site-scope";
import styles from "./AdminLayout.module.scss";

type AdminLayoutProps = {
  children: ReactNode;
};

// Below this width the sidebar becomes an off-canvas drawer (keep in sync with the media query in the scss).
const MOBILE_QUERY = "(max-width: 768px)";

function useIsMobile() {
  return useSyncExternalStore(
    (notify) => {
      const query = window.matchMedia(MOBILE_QUERY);
      query.addEventListener("change", notify);
      return () => query.removeEventListener("change", notify);
    },
    () => window.matchMedia(MOBILE_QUERY).matches,
    () => false,
  );
}

function AdminLayoutInner({ children }: AdminLayoutProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const isMobile = useIsMobile();
  const drawerOpen = isMobile && mobileOpen;
  const { selectedSite, setSelectedSite, siteCodes } = useSiteScope();

  useEffect(() => {
    if (!drawerOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [drawerOpen]);

  return (
    <div className={styles.adminContainer}>
      <AdminSidebar
        isCollapsed={isSidebarCollapsed && !isMobile}
        isMobile={isMobile}
        drawerOpen={drawerOpen}
        onNavigate={() => setMobileOpen(false)}
      />
      {drawerOpen && <div className={styles.backdrop} onClick={() => setMobileOpen(false)} aria-hidden="true" />}

      <div
        className={`${styles.mainWrapper} ${
          isSidebarCollapsed ? styles.sidebarCollapsed : ""
        }`}
      >
        <AdminHeader
          isSidebarCollapsed={isMobile ? !drawerOpen : isSidebarCollapsed}
          onToggleSidebar={() => (isMobile ? setMobileOpen((open) => !open) : setIsSidebarCollapsed(!isSidebarCollapsed))}
          selectedSite={selectedSite || ""}
          siteCodes={siteCodes}
          onSelectSite={setSelectedSite}
        />

        <main className={styles.contentArea}>{children}</main>

        <AdminFooter />
      </div>
    </div>
  );
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  return (
    <SiteScopeProvider>
      <AdminThemeProvider>
        <AdminLayoutInner>{children}</AdminLayoutInner>
      </AdminThemeProvider>
    </SiteScopeProvider>
  );
}

