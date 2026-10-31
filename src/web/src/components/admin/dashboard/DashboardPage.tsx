"use client";

import {
  SyncOutlined,
  SwapOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import MetricCards from "./sections/MetricCards";
import CampusStatusCards from "./sections/CampusStatusCards";
import RevenueOverview from "./sections/RevenueOverview";
import CourseDistribution from "./sections/CourseDistribution";
import RecentActivity from "./sections/RecentActivity";
import RecentEnrollmentsTable from "./sections/RecentEnrollmentsTable";
import styles from "./DashboardPage.module.scss";

export default function DashboardPage() {
  return (
    <div className={styles.dashboardContainer}>
      {/* Page Header */}
      <div className={styles.pageHeader}>
        <div className={styles.headerTitle}>
          <h1>Dashboard Quản Trị Hệ Thống</h1>
          <p>
            <span>Quản lý 3 cơ sở đào tạo ngoại ngữ (Q1, Q7, Thủ Đức)</span>
            <span className={styles.syncIndicator}>
              <span className={styles.dot} />
              <span>3/3 CSDL Đồng bộ</span>
            </span>
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.btnAction}
            title="Kích hoạt kiểm tra đồng bộ CSDL"
          >
            <SyncOutlined /> Kiểm tra kết nối
          </button>
          <a
            href="/admin/transfers"
            className={`${styles.btnAction} ${styles.primary}`}
          >
            <SwapOutlined /> Duyệt chuyển cơ sở (2PC)
          </a>
        </div>
      </div>

      {/* 4 Metric Cards */}
      <MetricCards />

      {/* 3 Campus Status Cards */}
      <CampusStatusCards />

      {/* Analytics row (Bar chart & distribution) */}
      <div className={styles.analyticsRow}>
        <RevenueOverview />
        <CourseDistribution />
      </div>

      {/* Bottom row (Recent enrollments table & Activity timeline) */}
      <div className={styles.bottomGrid}>
        <RecentEnrollmentsTable />
        <RecentActivity />
      </div>
    </div>
  );
}

