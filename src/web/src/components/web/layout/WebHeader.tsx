"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import styles from "./WebHeader.module.scss";

const links = [
  { href: "/programs", label: "Chương trình" },
  { href: "/courses", label: "Khóa học" },
  { href: "/blog", label: "Blog" },
  { href: "/contact", label: "Liên hệ" },
];

export default function WebHeader() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className={styles.header}>
      <a className={styles.skipLink} href="#main-content">Bỏ qua điều hướng</a>
      <div className={styles.inner}>
        <Link className={styles.brand} href="/" aria-label="[Tên trung tâm] — trang chủ" onClick={() => setMenuOpen(false)}>
          <span className={styles.brandMark} aria-hidden="true">N</span>
          <span className={styles.brandText}>[Tên trung tâm]<span>TRUNG TÂM NGOẠI NGỮ</span></span>
        </Link>

        <button
          className={styles.menuButton}
          type="button"
          aria-label={menuOpen ? "Đóng điều hướng" : "Mở điều hướng"}
          aria-expanded={menuOpen}
          aria-controls="public-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span /><span />
        </button>

        <nav id="public-navigation" className={`${styles.navigation} ${menuOpen ? styles.navigationOpen : ""}`} aria-label="Điều hướng chính">
          {links.map((link) => (
            <Link
              key={link.href}
              className={pathname === link.href || (link.href !== "/" && pathname.startsWith(`${link.href}/`)) ? styles.activeLink : undefined}
              href={link.href}
              onClick={() => setMenuOpen(false)}
            >
              {link.label}
            </Link>
          ))}
          <Link className={styles.loginLink} href="/login" onClick={() => setMenuOpen(false)}>
            Đăng nhập <span aria-hidden="true">↗</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}
