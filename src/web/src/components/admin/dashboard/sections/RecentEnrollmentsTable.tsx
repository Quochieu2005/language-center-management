"use client";

import Link from "next/link";
import styles from "../DashboardPage.module.scss";

type Enrollment = {
  id: string;
  studentCode: string;
  studentName: string;
  campus: string;
  course: string;
  fee: string;
  status: "paid" | "partial" | "pending";
  date: string;
};

export default function RecentEnrollmentsTable() {
  const enrollments: Enrollment[] = [
    {
      id: "1",
      studentCode: "Q1-HV-000102",
      studentName: "Nguyễn Văn An",
      campus: "Quận 1",
      course: "TOEIC Đột Phá 700+",
      fee: "4.500.000 đ",
      status: "paid",
      date: "15/10/2026",
    },
    {
      id: "2",
      studentCode: "Q7-HV-000089",
      studentName: "Trần Thị Mai",
      campus: "Quận 7",
      course: "IELTS Intensive 6.5",
      fee: "6.800.000 đ",
      status: "partial",
      date: "14/10/2026",
    },
    {
      id: "3",
      studentCode: "TD-HV-000215",
      studentName: "Lê Hoàng Long",
      campus: "Thủ Đức",
      course: "Giao Tiếp Phản Xạ Quốc Tế",
      fee: "3.200.000 đ",
      status: "paid",
      date: "14/10/2026",
    },
    {
      id: "4",
      studentCode: "Q1-HV-000095",
      studentName: "Phạm Thùy Linh",
      campus: "Quận 1",
      course: "Luyện Thi VSTEP B2",
      fee: "3.800.000 đ",
      status: "pending",
      date: "13/10/2026",
    },
    {
      id: "5",
      studentCode: "TD-HV-000188",
      studentName: "Vũ Quốc Bảo",
      campus: "Thủ Đức",
      course: "TOEIC Cấp Tốc 550+",
      fee: "3.500.000 đ",
      status: "paid",
      date: "12/10/2026",
    },
  ];

  const renderBadge = (status: Enrollment["status"]) => {
    switch (status) {
      case "paid":
        return <span className={`${styles.badge} ${styles.success}`}>Đã nộp đủ</span>;
      case "partial":
        return <span className={`${styles.badge} ${styles.warning}`}>Nộp đợt 1</span>;
      case "pending":
        return <span className={`${styles.badge} ${styles.danger}`}>Chờ nộp</span>;
    }
  };

  return (
    <div className={styles.tableCard}>
      <div className={styles.tableHeader}>
        <h3>Đăng ký khóa học mới nhất (Global Stream)</h3>
        <Link href="/admin/students">Xem tất cả học viên →</Link>
      </div>

      <div className={styles.tableWrapper}>
        <table className={styles.adminTable}>
          <thead>
            <tr>
              <th>Mã học viên</th>
              <th>Họ và tên</th>
              <th>Cơ sở</th>
              <th>Lớp / Khóa học</th>
              <th>Học phí</th>
              <th>Trạng thái</th>
              <th>Ngày ĐK</th>
            </tr>
          </thead>
          <tbody>
            {enrollments.map((e) => (
              <tr key={e.id}>
                <td>
                  <span className={styles.studentCode}>{e.studentCode}</span>
                </td>
                <td style={{ fontWeight: 600 }}>{e.studentName}</td>
                <td>
                  <span className={`${styles.badge} ${styles.site}`}>{e.campus}</span>
                </td>
                <td>{e.course}</td>
                <td>{e.fee}</td>
                <td>{renderBadge(e.status)}</td>
                <td style={{ color: "var(--admin-text-secondary)", fontSize: "12px" }}>
                  {e.date}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

