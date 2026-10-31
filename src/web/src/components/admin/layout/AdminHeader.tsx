"use client";

import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SearchOutlined,
  BellOutlined,
  FullscreenOutlined,
  GlobalOutlined,
  DownOutlined,
} from "@ant-design/icons";
import { useAdminTheme } from "../theme/AdminThemeContext";
import styles from "./AdminLayout.module.scss";

type AdminHeaderProps = {
  isSidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  selectedSite: string;
  onSelectSite: (site: string) => void;
};

export default function AdminHeader({
  isSidebarCollapsed,
  onToggleSidebar,
  selectedSite,
  onSelectSite,
}: AdminHeaderProps) {
  const { theme, toggleTheme } = useAdminTheme();

  return (
    <header className={styles.header}>
      <div className={styles.headerLeft}>
        <button
          type="button"
          className={styles.toggleBtn}
          onClick={onToggleSidebar}
          aria-label={isSidebarCollapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
          title={isSidebarCollapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
        >
          {isSidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        </button>

        <div className={styles.searchBox}>
          <SearchOutlined className={styles.searchIcon} />
          <input
            type="text"
            placeholder="Tìm kiếm học viên, lớp, giao dịch (Cmd + K)..."
            aria-label="Tìm kiếm nhanh"
          />
        </div>
      </div>

      <div className={styles.headerRight}>
        {/* Bộ chọn cơ sở cho Admin Big */}
        <div className={styles.campusSelector} title="Phạm vi truy vấn cơ sở">
          <GlobalOutlined style={{ color: "#2c746b" }} />
          <span>Cơ sở:</span>
          <select
            className={styles.campusSelect}
            value={selectedSite}
            onChange={(e) => onSelectSite(e.target.value)}
          >
            <option value="ALL">Toàn hệ thống (Q1, Q7, TD)</option>
            <option value="Q1">Quận 1 (QLTTNN_Q1)</option>
            <option value="Q7">Quận 7 (QLTTNN_Q7)</option>
            <option value="TD">Thủ Đức (QLTTNN_TD)</option>
          </select>
        </div>

        {/* Nút bật/tắt giao diện Sáng / Tối */}
        <button
          type="button"
          className={styles.themeToggleBtn}
          onClick={toggleTheme}
          title={theme === "dark" ? "Chuyển sang giao diện Sáng" : "Chuyển sang giao diện Tối"}
          aria-label="Chuyển đổi giao diện sáng tối"
        >
          <span className={styles.themeLabel}>{theme === "dark" ? "Tối" : "Sáng"}</span>
        </button>

        <button
          type="button"
          className={styles.iconBtn}
          title="Toàn màn hình"
          onClick={() => {
            if (!document.fullscreenElement) {
              document.documentElement.requestFullscreen().catch(() => {});
            } else {
              document.exitFullscreen().catch(() => {});
            }
          }}
        >
          <FullscreenOutlined />
        </button>

        <button
          type="button"
          className={styles.iconBtn}
          title="Thông báo hệ thống phân tán"
        >
          <BellOutlined />
          <span className={styles.notificationBadge}>3</span>
        </button>

        <div className={styles.userProfile} title="Thông tin người dùng">
          <div className={styles.avatar}>Q</div>
          <div className={styles.userInfo}>
            <span className={styles.userName}>Quốc Hiếu</span>
            <span className={styles.userRole}>Admin Big</span>
          </div>
          <DownOutlined style={{ fontSize: 10, color: "#71717a" }} />
        </div>
      </div>
    </header>
  );
}

