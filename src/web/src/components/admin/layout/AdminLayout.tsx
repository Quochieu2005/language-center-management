"use client";

import { useState, type ReactNode } from "react";
import AdminHeader from "./AdminHeader";
import AdminSidebar from "./AdminSidebar";
import AdminFooter from "./AdminFooter";
import { AdminThemeProvider } from "../theme/AdminThemeContext";
import { SiteScopeProvider, useSiteScope } from "@/lib/auth/site-scope";
import styles from "./AdminLayout.module.scss";

type AdminLayoutProps = {
  children: ReactNode;
};

function AdminLayoutInner({ children }: AdminLayoutProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const { selectedSite, setSelectedSite, siteCodes } = useSiteScope();

  return (
    <div className={styles.adminContainer}>
      <AdminSidebar isCollapsed={isSidebarCollapsed} />

      <div
        className={`${styles.mainWrapper} ${
          isSidebarCollapsed ? styles.sidebarCollapsed : ""
        }`}
      >
        <AdminHeader
          isSidebarCollapsed={isSidebarCollapsed}
          onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
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

