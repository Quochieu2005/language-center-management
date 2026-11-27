"use client";

import styles from "./AdminLayout.module.scss";

export default function AdminFooter() {
  return (
    <footer className={styles.footer}>
      <div>
        <span>CSDL phân tán SQL Server: mỗi cơ sở một database độc lập</span>
      </div>
      <div className={styles.footerLinks}>
        <span>Kiến trúc Coordinator (Django REST + Next.js)</span>
      </div>
    </footer>
  );
}

