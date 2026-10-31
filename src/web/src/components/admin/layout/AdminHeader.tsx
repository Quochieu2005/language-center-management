"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Button, Dropdown, Tag, Typography, message } from "antd";
import { BellOutlined, BulbOutlined, GlobalOutlined, MenuFoldOutlined, MenuUnfoldOutlined, SearchOutlined } from "@ant-design/icons";
import { adminApi } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";
import { useAdminTheme } from "../theme/AdminThemeContext";
import styles from "./AdminLayout.module.scss";

type AdminHeaderProps = {
  isSidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  selectedSite: string;
  siteCodes: string[];
  onSelectSite: (site: string) => void;
};

export default function AdminHeader({ isSidebarCollapsed, onToggleSidebar, selectedSite, siteCodes, onSelectSite }: AdminHeaderProps) {
  const { theme, toggleTheme } = useAdminTheme();
  const { user, signOut } = useSession();
  const { loadingSites } = useSiteScope();
  const router = useRouter();
  const [notifications, setNotifications] = useState<Record<string, unknown>[]>([]);
  const [notificationError, setNotificationError] = useState("");

  useEffect(() => {
    if (!user || !["admin_big", "admin_small"].includes(user.role)) return;
    adminApi.notifications({ limit: 10 }).then((data) => {
      setNotifications(data.results);
      setNotificationError(data.complete ? "" : `Thiếu dữ liệu từ: ${data.missing_sites.join(", ")}`);
    }).catch((error: unknown) => {
      setNotificationError(error instanceof Error ? error.message : "Không tải được thông báo.");
      if (error instanceof ApiError && Array.isArray(error.payload.results)) {
        setNotifications(error.payload.results.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object"));
      }
    });
  }, [user]);

  const notificationMenu = {
    items: notifications.length
      ? notifications.map((item, index) => ({
          key: String(item.slug ?? index),
          label: <div><strong>{String(item.title ?? "Thông báo")}</strong><div>{String(item.message ?? "")}</div><Typography.Text type="secondary">{String(item.site_code ?? "")}</Typography.Text></div>,
        }))
      : [{ key: "empty", label: notificationError || "Chưa có thông báo.", disabled: true }],
    onClick: ({ key }: { key: string }) => {
      const item = notifications.find((notice, index) => String(notice.slug ?? index) === key);
      if (typeof item?.target_path === "string" && item.target_path.startsWith("/")) router.push(item.target_path);
    },
  };
  const canSearchStudents = ["admin_big", "admin_small", "tu_van"].includes(user?.role || "");

  return <header className={styles.header}>
    <div className={styles.headerLeft}>
      <button type="button" className={styles.toggleBtn} onClick={onToggleSidebar} aria-label={isSidebarCollapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}>
        {isSidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
      </button>
      {canSearchStudents && <form className={styles.searchBox} onSubmit={(event) => {
        event.preventDefault();
        const value = new FormData(event.currentTarget).get("search")?.toString().trim();
        if (value) router.push(`/admin/students?search=${encodeURIComponent(value)}`);
      }}>
        <SearchOutlined className={styles.searchIcon} />
        <input name="search" type="search" placeholder="Tìm học viên theo tên, email hoặc mã" aria-label="Tìm học viên" />
      </form>}
    </div>

    <div className={styles.headerRight}>
      {user?.role === "admin_big" && <div className={styles.campusSelector} title="Cơ sở mà API sẽ truy vấn">
        <GlobalOutlined aria-hidden="true" />
        <span>Cơ sở:</span>
        <select className={styles.campusSelect} value={selectedSite} onChange={(event) => onSelectSite(event.target.value)} disabled={loadingSites || !siteCodes.length}>
          {siteCodes.map((site) => <option key={site} value={site}>{site}</option>)}
        </select>
      </div>}
      {user?.role !== "admin_big" && user?.site_code && <Tag color="blue">Cơ sở {user.site_code}</Tag>}

      {(user?.role === "admin_big" || user?.role === "admin_small") && <Dropdown menu={notificationMenu} trigger={["click"]} placement="bottomRight">
        <button type="button" className={styles.iconBtn} title={notificationError || "Thông báo"} aria-label="Thông báo">
          <Badge count={notifications.length} size="small"><BellOutlined /></Badge>
        </button>
      </Dropdown>}
      <Button className={styles.iconBtn} type="text" icon={<BulbOutlined />} onClick={toggleTheme} title={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"} aria-label="Đổi giao diện sáng tối" />

      <Dropdown menu={{ items: [
        { key: "profile", label: "Hồ sơ của tôi", onClick: () => router.push("/profile") },
        { key: "password", label: "Đổi mật khẩu", onClick: () => router.push("/password/change") },
        { type: "divider" },
        { key: "logout", label: "Đăng xuất", onClick: async () => { try { await signOut(); } catch { message.error("Không thu hồi được phiên trên máy chủ."); } } },
      ] }} trigger={["click"]}>
        <button type="button" className={styles.userProfile} title="Tài khoản">
          <div className={styles.avatar}>{(user?.username || user?.email || "U").slice(0, 1).toUpperCase()}</div>
          <div className={styles.userInfo}><span className={styles.userName}>{user?.username || user?.email}</span><span className={styles.userRole}>{roleTitle(user?.role)}</span></div>
        </button>
      </Dropdown>
    </div>
  </header>;
}

function roleTitle(role?: string) {
  return ({ admin_big: "Admin Big", admin_small: "Admin Small", le_tan: "Lễ tân", tu_van: "Tư vấn", ke_toan: "Kế toán", xep_lop: "Xếp lớp" } as Record<string, string>)[role || ""] || "Tài khoản";
}
