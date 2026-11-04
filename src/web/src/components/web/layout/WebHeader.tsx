"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./WebHeader.module.scss";

const NAV_ITEMS = [
  { href: "/", label: "Trang chủ" },
  { href: "/blog", label: "Blog" },
  { href: "/courses", label: "Chương trình khóa học" },
  { href: "/contact", label: "Liên hệ" },
];

export default function WebHeader() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const pathname = usePathname();

  return (
    <>
      {/* Top Announcement Bar */}
      <div className={styles.topBar}>
        <div className={styles.topBarInner}>
          <div className={styles.announcement}>
            <span className={styles.badge}>Tuyển sinh 2026</span>
            <span>Khóa học TOEIC, IELTS, giao tiếp và VSTEP tại TP. Hồ Chí Minh</span>
          </div>
          <div className={styles.topBarRight}>
            <a href="tel:0901234567" className={styles.contactItem}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
              <span>Tổng đài: 0901.234.567</span>
            </a>
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
                POLYGLOT
              </div>
              <div className={styles.brandTagline}>Trung tâm đào tạo ngoại ngữ</div>
            </div>
          </Link>

          <nav className={styles.nav}>
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.navLink} ${item.href === pathname ? styles.active : ""}`}
                aria-current={item.href === pathname ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className={styles.actions}>


            <Link href="/login" className={styles.adminBtn} title="Đăng nhập">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              <span>Đăng nhập</span>
            </Link>

            <Link href="/contact" className={styles.primaryCta}>
              <span>Đăng ký tư vấn</span>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </Link>
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
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.mobileNavLink} ${item.href === pathname ? styles.active : ""}`}
                aria-current={item.href === pathname ? "page" : undefined}
                onClick={() => setMobileMenuOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <div className={styles.mobileActions}>
              <Link href="/login" className={styles.adminBtn} onClick={() => setMobileMenuOpen(false)}>
                Đăng nhập
              </Link>
              <Link href="/contact" className={styles.primaryCta} onClick={() => setMobileMenuOpen(false)}>
                Đăng ký tư vấn ngay
              </Link>
            </div>
          </div>
        </div>
      </header>
    </>
  );
}
