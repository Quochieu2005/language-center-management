"use client";

import styles from "../DashboardPage.module.scss";

type CampusData = {
  id: string;
  code: string;
  name: string;
  address: string;
  dbName: string;
  students: number;
  classes: number;
  revenue: string;
  status: "active" | "warning" | "error";
  latency: string;
};

export default function CampusStatusCards() {
  const campuses: CampusData[] = [
    {
      id: "1",
      code: "Q1",
      name: "Cơ sở Quận 1 (Trụ sở chính)",
      address: "123 Lê Lợi, Phường Bến Nghé, Quận 1, TP.HCM",
      dbName: "QLTTNN_Q1",
      students: 542,
      classes: 24,
      revenue: "560.200.000 đ",
      status: "active",
      latency: "12ms",
    },
    {
      id: "2",
      code: "Q7",
      name: "Cơ sở Quận 7 (Nam Sài Gòn)",
      address: "456 Nguyễn Lương Bằng, Tân Phú, Quận 7, TP.HCM",
      dbName: "QLTTNN_Q7",
      students: 389,
      classes: 18,
      revenue: "412.800.000 đ",
      status: "active",
      latency: "15ms",
    },
    {
      id: "3",
      code: "TD",
      name: "Cơ sở Thủ Đức (Khu ĐHQG)",
      address: "789 Võ Văn Ngân, Linh Chiểu, TP. Thủ Đức, TP.HCM",
      dbName: "QLTTNN_TD",
      students: 453,
      classes: 20,
      revenue: "455.500.000 đ",
      status: "active",
      latency: "18ms",
    },
  ];

  return (
    <div className={styles.campusSection}>
      <div className={styles.sectionHeader}>
        <h2>Tình trạng CSDL 3 Cơ sở Phân tán</h2>
        <span className={styles.sectionMeta}>
          Mỗi cơ sở lưu trữ dữ liệu tại 1 SQL Server độc lập
        </span>
      </div>

      <div className={styles.campusGrid}>
        {campuses.map((c) => (
          <div key={c.id} className={styles.campusCard}>
            <div className={styles.campusTop}>
              <span className={styles.campusBadge}>Site {c.code}</span>
              <div className={styles.campusStatus}>
                <span className={styles.statusDot} />
                <span>Hoạt động</span>
                <span className={styles.latency}>({c.latency})</span>
              </div>
            </div>

            <div>
              <div className={styles.campusName}>{c.name}</div>
              <div className={styles.campusAddress}>{c.address}</div>
            </div>

            <div className={styles.campusStats}>
              <div className={styles.statItem}>
                <span className={styles.statVal}>{c.students}</span>
                <span className={styles.statLbl}>Học viên</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statVal}>{c.classes}</span>
                <span className={styles.statLbl}>Lớp học</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statVal} style={{ fontSize: "14px" }}>
                  {c.revenue}
                </span>
                <span className={styles.statLbl}>Doanh thu</span>
              </div>
            </div>

            <div className={styles.campusFooter}>
              <span>CSDL riêng:</span>
              <span className={styles.dbName}>{c.dbName}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

