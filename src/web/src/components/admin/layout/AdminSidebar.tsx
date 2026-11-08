"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  DashboardOutlined,
  TeamOutlined,
  CalendarOutlined,
  DollarCircleOutlined,
  SwapOutlined,
  BookOutlined,
  UsergroupAddOutlined,
  IdcardOutlined,
  BarChartOutlined,
  BellOutlined,
  FileSearchOutlined,
  PhoneOutlined,
  ReadOutlined,
} from "@ant-design/icons";
import styles from "./AdminLayout.module.scss";
import { useSession } from "@/lib/auth/session";
import type { Role } from "@/lib/api/auth";
import type { ReactNode } from "react";

type AdminSidebarProps = {
  isCollapsed: boolean;
};

type MenuItem = { label: string; href: string; icon: ReactNode; roles?: Role[]; openInNewTab?: boolean };
type MenuSection = { title: string; items: MenuItem[] };

export default function AdminSidebar({ isCollapsed }: AdminSidebarProps) {
  const pathname = usePathname();
  const { user } = useSession();

  const menuSections: MenuSection[] = [
    {
      title: "Tổng quan",
      items: [
        {
          label: "Dashboard",
          href: "/admin",
          icon: <DashboardOutlined />,
        },
      ],
    },
    {
      title: "Quản lý",
      items: [
        { label: "Hồ sơ học viên", href: "/admin/students", icon: <TeamOutlined />, roles: ["admin_big", "admin_small", "tu_van"] },
        { label: "Lớp học & Xếp lớp", href: "/admin/classes", icon: <CalendarOutlined />, roles: ["admin_big", "admin_small", "le_tan", "xep_lop", "tu_van"] },
        { label: "Giáo viên", href: "/admin/teachers", icon: <UsergroupAddOutlined />, roles: ["admin_big", "admin_small"] },
        { label: "Môn học dùng chung", href: "/admin/subjects", icon: <BookOutlined />, roles: ["admin_big"] },
        { label: "Khóa học", href: "/admin/courses", icon: <ReadOutlined />, roles: ["admin_big"] },
        { label: "Nhân viên", href: "/admin/employees", icon: <IdcardOutlined />, roles: ["admin_big", "admin_small"] },
        { label: "Quản lý Admin Small", href: "/admin/accounts", icon: <IdcardOutlined />, roles: ["admin_big"] },
        { label: "Chuyển cơ sở", href: "/admin/transfers", icon: <SwapOutlined />, roles: ["admin_big", "admin_small"] },
        { label: "Học phí & Thu tiền", href: "/admin/tuition", icon: <DollarCircleOutlined />, roles: ["admin_big", "admin_small", "ke_toan"] },
        { label: "Thống kê theo cơ sở", href: "/admin/reports", icon: <BarChartOutlined />, roles: ["admin_big", "admin_small"] },
      ],
    },
    {
      title: "Hệ thống & website",
      items: [
        { label: "Thông báo", href: "/admin/notifications", icon: <BellOutlined />, roles: ["admin_big", "admin_small"] },
        { label: "Nhật ký Admin", href: "/admin/audit", icon: <FileSearchOutlined />, roles: ["admin_big", "admin_small"] },
        { label: "Blog", href: "/blog", icon: <ReadOutlined />, openInNewTab: true },
        { label: "Liên hệ", href: "/contact", icon: <PhoneOutlined />, openInNewTab: true },
      ],
    },
  ];

  return (
    <aside className={`${styles.sidebar} ${isCollapsed ? styles.collapsed : ""}`}>
      {/* Brand logo / title */}
      <div className={styles.brandSection}>
        <div className={styles.brandLogo}>Z</div>
        <div className={styles.brandName}>
          <span className={styles.title}>Zenith Admin</span>
          <span className={styles.subtitle}>CSDL Phân tán</span>
        </div>
      </div>

      {/* Nav items */}
      <div className={styles.sidebarContent}>
        {menuSections.map((sec) => {
          const items = sec.items.filter((item) => !item.roles || item.roles.includes(user?.role as Role));
          if (!items.length) return null;
          return (
            <div key={sec.title} className={styles.menuGroup}>
              <div className={styles.groupTitle}>{sec.title}</div>
              <ul className={styles.menuList}>
                {items.map((item) => {
                  const isActive =
                    pathname === item.href ||
                    (item.href !== "/admin" && pathname?.startsWith(item.href));

                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        target={item.openInNewTab ? "_blank" : undefined}
                        rel={item.openInNewTab ? "noopener noreferrer" : undefined}
                        className={`${styles.menuItem} ${isActive ? styles.active : ""}`}
                        title={item.label}
                      >
                        <span className={styles.menuIcon}>{item.icon}</span>
                        <span className={styles.menuLabel}>{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
    </aside>
  );
}

