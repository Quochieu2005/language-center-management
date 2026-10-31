"use client";

import { useState, type ReactNode } from "react";
import AdminHeader from "./AdminHeader";
import AdminSidebar from "./AdminSidebar";
import AdminFooter from "./AdminFooter";
import { AdminThemeProvider } from "../theme/AdminThemeContext";
import styles from "./AdminLayout.module.scss";

type AdminLayoutProps = {
  children: ReactNode;
};

function AdminLayoutInner({ children }: AdminLayoutProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [selectedSite, setSelectedSite] = useState("ALL");

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
          selectedSite={selectedSite}
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
    <AdminThemeProvider>
      <AdminLayoutInner>{children}</AdminLayoutInner>
    </AdminThemeProvider>
  );
}

