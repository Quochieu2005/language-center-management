"use client";

import {
  TeamOutlined,
  BookOutlined,
  DollarCircleOutlined,
  CloudSyncOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
} from "@ant-design/icons";
import styles from "../DashboardPage.module.scss";

type MetricItem = {
  label: string;
  value: string;
  trend: string;
  trendDirection: "up" | "down" | "neutral";
  trendDesc: string;
  icon: React.ReactNode;
  colorScheme: "petrol" | "blue" | "emerald" | "amber";
};

export default function MetricCards() {
  const metrics: MetricItem[] = [
    {
      label: "Tổng học viên đang học",
      value: "1,384",
      trend: "+12.5%",
      trendDirection: "up",
      trendDesc: "so với tháng trước",
      icon: <TeamOutlined />,
      colorScheme: "petrol",
    },
    {
      label: "Lớp học đang mở",
      value: "62",
      trend: "+4 lớp",
      trendDirection: "up",
      trendDesc: "tại 3 cơ sở Q1, Q7, TD",
      icon: <BookOutlined />,
      colorScheme: "blue",
    },
    {
      label: "Doanh thu tháng (VNĐ)",
      value: "1.428.500.000",
      trend: "+8.2%",
      trendDirection: "up",
      trendDesc: "toàn bộ 3 cơ sở",
      icon: <DollarCircleOutlined />,
      colorScheme: "emerald",
    },
    {
      label: "Đồng bộ nhân bản CSDL",
      value: "100%",
      trend: "Hoàn tất",
      trendDirection: "neutral",
      trendDesc: "3/3 SQL Server Sites",
      icon: <CloudSyncOutlined />,
      colorScheme: "amber",
    },
  ];

  return (
    <div className={styles.metricsGrid}>
      {metrics.map((item, idx) => (
        <div key={idx} className={styles.metricCard}>
          <div className={styles.metricInfo}>
            <span className={styles.metricLabel}>{item.label}</span>
            <span className={styles.metricValue}>{item.value}</span>
            <div className={`${styles.metricTrend} ${styles[item.trendDirection]}`}>
              {item.trendDirection === "up" && <ArrowUpOutlined />}
              {item.trendDirection === "down" && <ArrowDownOutlined />}
              <span>{item.trend}</span>
              <span className={styles.trendDesc}>{item.trendDesc}</span>
            </div>
          </div>
          <div className={`${styles.metricIconWrapper} ${styles[item.colorScheme]}`}>
            {item.icon}
          </div>
        </div>
      ))}
    </div>
  );
}

