"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import styles from "./WebHeader.module.scss";
import { BRAND_INITIAL, BRAND_NAME } from "@/lib/brand";
import type { Role } from "@/lib/api/auth";
import { homeForRole, useSession } from "@/lib/auth/session";

const links = [
  { href: "/programs", label: "Chương trình" },
  { href: "/courses", label: "Khóa học" },
  { href: "/blog", label: "Blog" },
  { href: "/contact", label: "Liên hệ" },
];

function portalLabel(role: Role): string {
  if (role === "giao_vien") return "Cổng giáo viên";
  if (role === "hoc_vien") return "Cổng học viên";
  return "Trang quản trị";
}

export default function WebHeader() {
  const pathname = usePathname();
  const { user, loading } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className={styles.header}>
      <a className={styles.skipLink} href="#main-content">Bỏ qua điều hướng</a>
      <div className={styles.inner}>
        <Link className={styles.brand} href="/" aria-label={`${BRAND_NAME} — trang chủ`} onClick={() => setMenuOpen(false)}>
          <span className={styles.brandMark} aria-hidden="true">{BRAND_INITIAL}</span>
          <span className={styles.brandText}>{BRAND_NAME}<span>TRUNG TÂM NGOẠI NGỮ</span></span>
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
          {(user?.role === "hoc_vien" ? [...links, { href: "/account", label: "Hồ sơ" }] : links).map((link) => (
            <Link
              key={link.href}
              className={pathname === link.href || (link.href !== "/" && pathname.startsWith(`${link.href}/`)) ? styles.activeLink : undefined}
              href={link.href}
              onClick={() => setMenuOpen(false)}
            >
              {link.label}
            </Link>
          ))}
          {/* Signed-in users go straight to their own area; hidden (not removed) while the session loads to avoid layout shift. */}
          <Link
            className={styles.loginLink}
            href={user ? homeForRole(user.role) : "/login"}
            style={loading ? { visibility: "hidden" } : undefined}
            onClick={() => setMenuOpen(false)}
          >
            {user ? portalLabel(user.role) : "Đăng nhập"} <span aria-hidden="true">↗</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}
