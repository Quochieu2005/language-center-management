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
  FileTextOutlined,
} from "@ant-design/icons";
import styles from "./AdminLayout.module.scss";

type AdminSidebarProps = {
  isCollapsed: boolean;
};

export default function AdminSidebar({ isCollapsed }: AdminSidebarProps) {
  const pathname = usePathname();

  const menuSections = [
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
        },
        {
          label: "Lớp học & Xếp lớp",
          href: "/admin/classes",
          icon: <CalendarOutlined />,
          badge: null,
        },
        {
          label: "Chuyển cơ sở",
          href: "/admin/transfers",
          icon: <SwapOutlined />,
          badge: { text: "2PC", type: "hot" },
        },
        {
          label: "Học phí & Thu tiền",
          href: "/admin/tuition",
          icon: <DollarCircleOutlined />,
          badge: null,
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
        },
        {
          label: "Giảng viên & Roster",
          href: "/admin/teachers",
          icon: <UsergroupAddOutlined />,
          badge: null,
        },
        {
          label: "Quản trị cơ sở",
          href: "/admin/accounts",
          icon: <IdcardOutlined />,
          badge: null,
        },
      ],
    },
    {
      title: "Báo cáo & Kiểm toán",
      items: [
        {
          label: "Thống kê toàn cục",
          href: "/admin/reports",
          icon: <BarChartOutlined />,
          badge: null,
        },
        {
          label: "Nhật ký phân tán",
          href: "/admin/audit",
          icon: <FileTextOutlined />,
          badge: null,
        },
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
        {menuSections.map((sec, secIdx) => (
          <div key={secIdx} className={styles.menuGroup}>
            <div className={styles.groupTitle}>{sec.title}</div>
            <ul className={styles.menuList}>
              {sec.items.map((item, itemIdx) => {
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
        ))}
      </div>
    </aside>
  );
}

