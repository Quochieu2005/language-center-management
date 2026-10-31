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
} from "@ant-design/icons";
import styles from "./AdminLayout.module.scss";
import { useSession } from "@/lib/auth/session";
import type { Role } from "@/lib/api/auth";
import type { ReactNode } from "react";

type AdminSidebarProps = {
  isCollapsed: boolean;
};

type MenuItem = { label: string; href: string; icon: ReactNode; badge: { text: string; type: "hot" | "new" | "count" } | null; roles?: Role[] };
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
          badge: null,
        },
      ],
    },
    {
      title: "Nghiệp vụ phân tán",
      items: [
        {
          label: "Hồ sơ học viên",
          href: "/admin/students",
          icon: <TeamOutlined />,
          badge: { text: "Global", type: "count" },
          roles: ["admin_big", "admin_small", "tu_van"],
        },
        {
          label: "Lớp học & Xếp lớp",
          href: "/admin/classes",
          icon: <CalendarOutlined />,
          badge: null,
          roles: ["admin_big", "admin_small", "le_tan", "xep_lop", "tu_van"],
        },
        {
          label: "Chuyển cơ sở",
          href: "/admin/transfers",
          icon: <SwapOutlined />,
          badge: { text: "2PC", type: "hot" },
          roles: ["admin_big", "admin_small"],
        },
        {
          label: "Học phí & Thu tiền",
          href: "/admin/tuition",
          icon: <DollarCircleOutlined />,
          badge: null,
          roles: ["admin_big", "admin_small", "ke_toan"],
        },
      ],
    },
    {
      title: "Danh mục & Nhân sự",
      items: [
        {
          label: "Môn học dùng chung",
          href: "/admin/subjects",
          icon: <BookOutlined />,
          badge: { text: "Sync", type: "new" },
          roles: ["admin_big"],
        },
        {
          label: "Giảng viên & Roster",
          href: "/admin/teachers",
          icon: <UsergroupAddOutlined />,
          badge: null,
          roles: ["admin_big", "admin_small"],
        },
        {
          label: "Quản trị cơ sở",
          href: "/admin/accounts",
          icon: <IdcardOutlined />,
          badge: null,
          roles: ["admin_big", "admin_small"],
        },
      ],
    },
    {
      title: "Báo cáo",
      items: [{ label: "Thống kê theo cơ sở", href: "/admin/reports", icon: <BarChartOutlined />, badge: null, roles: ["admin_big", "admin_small"] }],
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
        {menuSections.map((sec, secIdx) => {
          const items = sec.items.filter((item) => !item.roles || item.roles.includes(user?.role as Role));
          if (!items.length) return null;
          return (
          <div key={secIdx} className={styles.menuGroup}>
            <div className={styles.groupTitle}>{sec.title}</div>
            <ul className={styles.menuList}>
              {items.map((item, itemIdx) => {
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/admin" && pathname?.startsWith(item.href));

                return (
                  <li key={itemIdx}>
                    <Link
                      href={item.href}
                      className={`${styles.menuItem} ${isActive ? styles.active : ""}`}
                      title={item.label}
                    >
                      <span className={styles.menuIcon}>{item.icon}</span>
                      <span className={styles.menuLabel}>{item.label}</span>
                      {item.badge && (
                        <span
                          className={`${styles.menuBadge} ${
                            item.badge.type === "hot"
                              ? styles.hot
                              : item.badge.type === "new"
                              ? styles.new
                              : styles.count
                          }`}
                        >
                          {item.badge.text}
                        </span>
                      )}
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

