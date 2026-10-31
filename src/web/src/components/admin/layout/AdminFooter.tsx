"use client";

import styles from "./AdminLayout.module.scss";

export default function AdminFooter() {
  return (
    <footer className={styles.footer}>
      <div>
        <span>CSDL Phân tán SQL Server: </span>
        <strong style={{ color: "#2c746b" }}>QLTTNN_Q1</strong> (12ms) ·{" "}
        <strong style={{ color: "#3b82f6" }}>QLTTNN_Q7</strong> (15ms) ·{" "}
        <strong style={{ color: "#f59e0b" }}>QLTTNN_TD</strong> (18ms)
      </div>
      <div className={styles.footerLinks}>
        <span>Kiến trúc Coordinator (Django REST + Next.js)</span>
      </div>
    </footer>
  );
}

