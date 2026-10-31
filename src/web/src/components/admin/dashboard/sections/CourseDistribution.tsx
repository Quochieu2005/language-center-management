"use client";

import styles from "../DashboardPage.module.scss";

export default function CourseDistribution() {
  const courses = [
    { name: "Tiếng Anh TOEIC", percent: 38, count: "525 HV", color: "#2c746b" },
    { name: "Tiếng Anh IELTS", percent: 32, count: "442 HV", color: "#3b82f6" },
    { name: "Giao tiếp Quốc tế", percent: 18, count: "250 HV", color: "#10b981" },
    { name: "Tiếng Anh VSTEP", percent: 12, count: "167 HV", color: "#f59e0b" },
  ];

  return (
    <div className={styles.chartCard}>
      <div className={styles.chartHeader}>
        <div>
          <h3>Phân bổ Khóa học</h3>
          <span style={{ fontSize: "12px", color: "var(--admin-text-secondary)" }}>
            Tỷ lệ học viên đang học
          </span>
        </div>
      </div>

      <div className={styles.distList}>
        {courses.map((c, i) => (
          <div key={i} className={styles.distItem}>
            <div className={styles.distMeta}>
              <span>{c.name}</span>
              <span className={styles.distPercent}>
                {c.count} ({c.percent}%)
              </span>
            </div>
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{ width: `${c.percent}%`, backgroundColor: c.color }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

