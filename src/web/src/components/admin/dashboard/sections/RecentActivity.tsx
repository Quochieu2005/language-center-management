"use client";

import {
  SwapOutlined,
  SyncOutlined,
  DollarCircleOutlined,
} from "@ant-design/icons";
import styles from "../DashboardPage.module.scss";

type ActivityItem = {
  id: string;
  type: "transfer" | "replicate" | "payment";
  title: string;
  desc: string;
  time: string;
  site: string;
};

export default function RecentActivity() {
  const activities: ActivityItem[] = [
    {
      id: "1",
      type: "transfer",
      title: "Giao dịch chuyển cơ sở hoàn tất",
      desc: "HV Q1-HV-000102 chuyển từ Cơ sở Q1 sang Q7 thành công (2PC)",
      time: "10 phút trước",
      site: "Q1 ➔ Q7",
    },
    {
      id: "2",
      type: "replicate",
      title: "Nhân bản môn học (Replicated-Write)",
      desc: "Coordinator đồng bộ cập nhật bảng MonHoc tới 3 site",
      time: "35 phút trước",
      site: "Q1, Q7, TD",
    },
    {
      id: "3",
      type: "payment",
      title: "Đóng học phí tại quầy",
      desc: "Thu học phí lớp TOEIC 700 - HV TD-HV-000045 (4.500.000 đ)",
      time: "1 giờ trước",
      site: "Thủ Đức",
    },
    {
      id: "4",
      type: "transfer",
      title: "Đề nghị chuyển cơ sở mới",
      desc: "Admin Small Q7 gửi đề nghị chuyển cơ sở cho học viên",
      time: "2 giờ trước",
      site: "Q7",
    },
  ];

  return (
    <div className={styles.activityCard}>
      <div className={styles.tableHeader}>
        <h3>Nhật ký hoạt động Phân tán</h3>
        <span style={{ fontSize: "12px", color: "var(--admin-text-muted)" }}>
          dbo.Logs 3 Site
        </span>
      </div>

      <div className={styles.timeline}>
        {activities.map((a) => (
          <div key={a.id} className={styles.timelineItem}>
            <div className={`${styles.timelineDot} ${styles[a.type]}`}>
              {a.type === "transfer" && <SwapOutlined />}
              {a.type === "replicate" && <SyncOutlined />}
              {a.type === "payment" && <DollarCircleOutlined />}
            </div>
            <div className={styles.timelineBody}>
              <div className={styles.timelineTitle}>{a.title}</div>
              <div className={styles.timelineDesc}>{a.desc}</div>
              <div className={styles.timelineTime}>
                <span>{a.time}</span> ·{" "}
                <span style={{ color: "#2c746b", fontWeight: 600 }}>{a.site}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

