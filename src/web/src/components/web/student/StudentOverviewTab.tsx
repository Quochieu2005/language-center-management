"use client";

import { Card, Statistic, Tag, Typography, Button, Space, Empty } from "antd";
import {
  BookOutlined,
  CalendarOutlined,
  DollarCircleOutlined,
  TrophyOutlined,
  EnvironmentOutlined,
  UserOutlined,
  ClockCircleOutlined,
  RightOutlined
} from "@ant-design/icons";
import type { ApiRow } from "@/lib/api/academics";
import styles from "./StudentPortal.module.scss";

type Props = {
  profile: ApiRow | null;
  enrollments: ApiRow[];
  schedule: ApiRow[];
  tuition: ApiRow[];
  grades: ApiRow[];
  onSelectTab: (key: string) => void;
};

export function StudentOverviewTab({
  profile,
  enrollments,
  schedule,
  tuition,
  grades,
  onSelectTab
}: Props) {
  // Tinh toan diem trung binh
  const avgGrade =
    grades.length > 0
      ? (
          grades.reduce((acc, curr) => acc + Number(curr.score || 0), 0) /
          grades.length
        ).toFixed(1)
      : null;

  // Tim buoi hoc tiep theo
  const upcomingSession = schedule.find(
    (item) => item.status === "du_kien" || item.status === "chua_hoc"
  ) || schedule[0];

  // Tong hoc phi con no
  const totalBalance = tuition.reduce(
    (acc, curr) => acc + Number(curr.balance || 0),
    0
  );

  return (
    <div style={{ display: "grid", gap: 24 }}>
      {/* 1. KPI Cards */}
      <div className={styles.kpiGrid}>
        <Card className={styles.kpiCard}>
          <Statistic
            title="Lớp đang tham gia"
            value={enrollments.length}
            prefix={<BookOutlined style={{ color: "#1677ff" }} />}
            suffix="lớp"
          />
          <Button
            type="link"
            size="small"
            style={{ padding: 0, marginTop: 8 }}
            onClick={() => onSelectTab("courses")}
          >
            Xem danh sách lớp <RightOutlined />
          </Button>
        </Card>

        <Card className={styles.kpiCard}>
          <Statistic
            title="Buổi học tiếp theo"
            value={upcomingSession ? String(upcomingSession.date || "Chưa có") : "Không có"}
            prefix={<CalendarOutlined style={{ color: "#52c41a" }} />}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {upcomingSession
              ? `${upcomingSession.start_time} · ${upcomingSession.room_name || "Phòng học"}`
              : "Hiện chưa có lịch mới"}
          </Typography.Text>
        </Card>

        <Card className={styles.kpiCard}>
          <Statistic
            title="Học phí còn nợ"
            value={totalBalance}
            precision={0}
            formatter={(val) => `${Number(val).toLocaleString("vi-VN")} ₫`}
            prefix={<DollarCircleOutlined style={{ color: totalBalance > 0 ? "#faad14" : "#52c41a" }} />}
          />
          <Button
            type="link"
            size="small"
            style={{ padding: 0, marginTop: 8 }}
            onClick={() => onSelectTab("tuition")}
          >
            {totalBalance > 0 ? "Chi tiết & Thanh toán" : "Lịch sử học phí"} <RightOutlined />
          </Button>
        </Card>

        <Card className={styles.kpiCard}>
          <Statistic
            title="Điểm trung bình"
            value={avgGrade || "Chưa có"}
            prefix={<TrophyOutlined style={{ color: "#fa8c16" }} />}
            suffix={avgGrade ? "/ 10" : ""}
          />
          <Button
            type="link"
            size="small"
            style={{ padding: 0, marginTop: 8 }}
            onClick={() => onSelectTab("grades")}
          >
            Xem bảng điểm <RightOutlined />
          </Button>
        </Card>
      </div>

      {/* 2. Hai cot noi dung: Lop dang hoc & Lich hoc gan nhat */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 24 }}>
        {/* Cot trai: Lop hoc */}
        <Card
          title={
            <Space>
              <BookOutlined style={{ color: "#175245" }} />
              <span>Khóa học & Lớp học đang tham gia</span>
            </Space>
          }
          extra={
            <Button type="link" onClick={() => onSelectTab("courses")}>
              Xem tất cả
            </Button>
          }
        >
          {enrollments.length === 0 ? (
            <Empty description="Bạn chưa đăng ký lớp học nào." />
          ) : (
            enrollments.slice(0, 2).map((item, index) => (
              <div key={String(item.enrollment_id || index)} className={styles.sessionItem}>
                <div className={styles.sessionDetails}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <Typography.Title level={5} style={{ margin: 0, color: "#175245" }}>
                      {String(item.class_name || item.course_name || "Lớp học")}
                    </Typography.Title>
                    <Tag color="green">Đang theo học</Tag>
                  </div>
                  <p>
                    <strong>Khóa học:</strong> {String(item.course_name || item.subject_name || "---")}
                  </p>
                  <p>
                    <ClockCircleOutlined /> Lịch học: {String(item.schedule || "---")} ({String(item.start_time || "")} - {String(item.end_time || "")})
                  </p>
                </div>
              </div>
            ))
          )}
        </Card>

        {/* Cot phai: Buoi hoc sap toi */}
        <Card
          title={
            <Space>
              <CalendarOutlined style={{ color: "#175245" }} />
              <span>Lịch học sắp tới</span>
            </Space>
          }
          extra={
            <Button type="link" onClick={() => onSelectTab("schedule")}>
              Xem thời khóa biểu
            </Button>
          }
        >
          {schedule.length === 0 ? (
            <Empty description="Chưa có lịch học được xếp." />
          ) : (
            schedule.slice(0, 3).map((item, index) => (
              <div key={String(item.session_id || index)} className={styles.sessionItem}>
                <div className={styles.sessionTime}>
                  <div>{String(item.date || "---")}</div>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {String(item.start_time || "")} - {String(item.end_time || "")}
                  </Typography.Text>
                </div>
                <div className={styles.sessionDetails}>
                  <Typography.Text strong>{String(item.class_name || "Lớp học")}</Typography.Text>
                  <div>
                    <EnvironmentOutlined /> {String(item.room_name || "Chưa xếp phòng")} · <UserOutlined /> {String(item.teacher_name || "Giảng viên")}
                  </div>
                  {Boolean(item.ghi_chu) && (
                    <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: "4px 0 0" }}>
                      {String(item.ghi_chu)}
                    </Typography.Paragraph>
                  )}
                </div>
                <div>
                  <Tag color={item.status === "da_hoc" ? "default" : "blue"}>
                    {item.status === "da_hoc" ? "Đã học" : "Sắp tới"}
                  </Tag>
                </div>
              </div>
            ))
          )}
        </Card>
      </div>

      {/* 3. Thong tin hoc vien */}
      <Card
        title={
          <Space>
            <UserOutlined style={{ color: "#175245" }} />
            <span>Thông tin cá nhân học viên</span>
          </Space>
        }
        extra={
          <Button type="link" onClick={() => onSelectTab("profile")}>
            Chỉnh sửa thông tin
          </Button>
        }
      >
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
          <div>
            <Typography.Text type="secondary">Họ và tên</Typography.Text>
            <div style={{ fontWeight: 600 }}>{String(profile?.full_name || "---")}</div>
          </div>
          <div>
            <Typography.Text type="secondary">Mã học viên</Typography.Text>
            <div style={{ fontWeight: 600, color: "#175245" }}>{String(profile?.student_id || "---")}</div>
          </div>
          <div>
            <Typography.Text type="secondary">Cơ sở đào tạo</Typography.Text>
            <div>
              <Tag color="cyan">{String(profile?.site_code || "TD")}</Tag>
            </div>
          </div>
          <div>
            <Typography.Text type="secondary">Số điện thoại</Typography.Text>
            <div style={{ fontWeight: 600 }}>{String(profile?.phone || "Chưa cập nhật")}</div>
          </div>
          <div>
            <Typography.Text type="secondary">Email liên hệ</Typography.Text>
            <div style={{ fontWeight: 600 }}>{String(profile?.email || "Chưa cập nhật")}</div>
          </div>
          <div>
            <Typography.Text type="secondary">Địa chỉ cư trú</Typography.Text>
            <div>{String(profile?.address || "Chưa cập nhật")}</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
