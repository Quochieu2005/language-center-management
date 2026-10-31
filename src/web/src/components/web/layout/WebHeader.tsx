"use client";

import React, { useState } from "react";
import Link from "next/link";
import styles from "./WebHeader.module.scss";

export default function WebHeader() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <>
      {/* Top Announcement Bar */}
      <div className={styles.topBar}>
        <div className={styles.topBarInner}>
          <div className={styles.announcement}>
            <span className={styles.badge}>Tuyển sinh 2026</span>
            <span>Hệ thống 3 cơ sở (Q1, Q7, TD) mở lớp mới - Đồng bộ CSDL trực tiếp</span>
          </div>
          <div className={styles.topBarRight}>
            <a href="tel:19008899" className={styles.contactItem}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
              <span>Tổng đài: 1900 8899</span>
            </a>
            <div className={styles.statusItem}>
              <span className={styles.statusDot} />
              <span>3 Site Đang Hoạt Động (Q1 · Q7 · TD)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Navigation Header */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand}>
            <div className={styles.brandLogo}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div className={styles.brandText}>
              <div className={styles.brandName}>
                POLYGLOT <span>DISTRIBUTED</span>
              </div>
              <div className={styles.brandTagline}>Hệ thống Đào tạo Phân tán 3 Cơ sở</div>
            </div>
          </Link>

          <nav className={styles.nav}>
            <Link href="/" className={`${styles.navLink} ${styles.active}`}>
              Trang chủ
            </Link>
            <a href="#courses" className={styles.navLink}>
              Khóa học
            </a>
            <a href="#branches" className={styles.navLink}>
              3 Cơ sở
            </a>
            <a href="#technology" className={styles.navLink}>
              Công nghệ phân tán
            </a>
            <a href="#faq" className={styles.navLink}>
              Hỏi đáp
            </a>
            <a href="#consultation" className={styles.navLink}>
              Liên hệ
            </a>
          </nav>

          <div className={styles.actions}>
            <a href="tel:0901234567" className={styles.hotlineBtn}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
              <span>0901.234.567</span>
            </a>

            <Link href="/admin" className={styles.adminBtn} title="Cổng điều hành Cán bộ & Quản trị viên">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              <span>Cán bộ / Admin</span>
            </Link>

            <a href="#consultation" className={styles.primaryCta}>
              <span>Đăng ký tư vấn</span>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </a>
          </div>

          <button
            type="button"
            className={styles.mobileMenuBtn}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Mở menu"
          >
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="24" height="24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={mobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
            </svg>
          </button>

          <div className={`${styles.mobileDrawer} ${mobileMenuOpen ? styles.open : ""}`}>
            <a href="#courses" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>
              Khóa học
            </a>
            <a href="#branches" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>
              3 Cơ sở đào tạo
            </a>
            <a href="#technology" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>
              Công nghệ phân tán
            </a>
            <a href="#faq" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>
              Hỏi đáp
            </a>
            <div className={styles.mobileActions}>
              <Link href="/admin" className={styles.adminBtn} onClick={() => setMobileMenuOpen(false)}>
                Cổng Cán bộ / Admin
              </Link>
              <a href="#consultation" className={styles.primaryCta} onClick={() => setMobileMenuOpen(false)}>
                Đăng ký tư vấn ngay
              </a>
            </div>
          </div>
        </div>
      </header>
    </>
  );
}
