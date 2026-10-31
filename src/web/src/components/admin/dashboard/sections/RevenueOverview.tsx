"use client";

import styles from "../DashboardPage.module.scss";

export default function RevenueOverview() {
  const monthsData = [
    { month: "T5", q1: 65, q7: 45, td: 50 },
    { month: "T6", q1: 75, q7: 55, td: 60 },
    { month: "T7", q1: 85, q7: 60, td: 70 },
    { month: "T8", q1: 95, q7: 70, td: 80 },
    { month: "T9", q1: 90, q7: 65, td: 75 },
    { month: "T10", q1: 100, q7: 75, td: 85 },
  ];

  return (
    <div className={styles.chartCard}>
      <div className={styles.chartHeader}>
        <div>
          <h3>Doanh thu theo Cơ sở (Global Query)</h3>
          <span style={{ fontSize: "12px", color: "var(--admin-text-secondary)" }}>
            So sánh doanh thu thực thu giữa các site (triệu VNĐ)
          </span>
        </div>
        <div className={styles.chartLegend}>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: "#2c746b" }} />
            <span>Q1</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: "#3b82f6" }} />
            <span>Q7</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ backgroundColor: "#f59e0b" }} />
            <span>Thủ Đức</span>
          </div>
        </div>
      </div>

      <div className={styles.barChartContainer}>
        {monthsData.map((d, i) => (
          <div key={i} className={styles.barGroup}>
            <div className={styles.barsWrapper}>
              <div
                className={`${styles.barCol} ${styles.q1}`}
                style={{ height: `${d.q1}%` }}
                title={`Quận 1: ${d.q1 * 5.6} tr`}
              />
              <div
                className={`${styles.barCol} ${styles.q7}`}
                style={{ height: `${d.q7}%` }}
                title={`Quận 7: ${d.q7 * 5.5} tr`}
              />
              <div
                className={`${styles.barCol} ${styles.td}`}
                style={{ height: `${d.td}%` }}
                title={`Thủ Đức: ${d.td * 5.3} tr`}
              />
            </div>
            <span className={styles.barLabel}>{d.month}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

