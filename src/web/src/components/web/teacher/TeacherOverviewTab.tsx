"use client";

import { Card, Statistic, Button, Tag, Empty, Progress } from "antd";
import {
  ReadOutlined,
  CalendarOutlined,
  TeamOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  RightOutlined,
} from "@ant-design/icons";
import type { ApiRow, SessionRow } from "@/lib/api/academics";
import styles from "./TeacherPortal.module.scss";

type TeacherOverviewTabProps = {
  classes: ApiRow[];
  sessions: SessionRow[];
  nextSession: SessionRow | null;
  onNavigateAttendance: (classItem: ApiRow, sessionItem?: SessionRow) => void;
  onNavigateClasses: () => void;
};

export function TeacherOverviewTab({
  classes,
  sessions,
  nextSession,
  onNavigateAttendance,
  onNavigateClasses,
}: TeacherOverviewTabProps) {
  const totalStudents = classes.reduce((sum, item) => sum + (Number(item.current_count) || 0), 0);
  const activeClasses = classes.filter((item) => String(item.status) === "dang_hoc").length;

  return (
    <div>
      {/* KPI Cards */}
      <div className={styles.kpiGrid}>
        <Card className={styles.kpiCard} variant="borderless">
          <Statistic
            title="Lớp đang phụ trách"
            value={classes.length}
            prefix={<ReadOutlined style={{ color: "#3b82f6" }} />}
            suffix={<span style={{ fontSize: 13, color: "#64748b" }}>({activeClasses} đang học)</span>}
          />
        </Card>
        <Card className={styles.kpiCard} variant="borderless">
          <Statistic
            title="Buổi học đã lên lịch"
            value={sessions.length}
            prefix={<CalendarOutlined style={{ color: "#8b5cf6" }} />}
          />
        </Card>
        <Card className={styles.kpiCard} variant="borderless">
          <Statistic
            title="Tổng số học viên"
            value={totalStudents}
            prefix={<TeamOutlined style={{ color: "#10b981" }} />}
          />
        </Card>
        <Card className={styles.kpiCard} variant="borderless">
          <Statistic
            title="Cơ sở làm việc"
            value="Thủ Đức"
            prefix={<EnvironmentOutlined style={{ color: "#f59e0b" }} />}
            suffix={<span style={{ fontSize: 13, color: "#64748b" }}>(TD)</span>}
          />
        </Card>
      </div>

      {/* Next Session Highlight */}
      {nextSession ? (
        <div className={styles.nextSessionCard}>
          <div className={styles.leftSection}>
            <div className={styles.iconWrapper}>
              <ClockCircleOutlined />
            </div>
            <div className={styles.info}>
              <h4>Buổi học kế tiếp · Buổi #{String((nextSession as Record<string, unknown>).sequence ?? nextSession.session_number ?? "")}</h4>
              <p>
                <strong>Ngày:</strong> {String((nextSession as Record<string, unknown>).session_date ?? nextSession.date ?? "")} &nbsp;|&nbsp;
                <strong>Giờ:</strong> {String(nextSession.start_time || "")} – {String(nextSession.end_time || "")} &nbsp;|&nbsp;
                <strong>Phòng:</strong> {String(nextSession.room_name || "Chưa phân phòng")}
              </p>
            </div>
          </div>
          <div>
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => {
                if (classes.length > 0) {
                  onNavigateAttendance(classes[0], nextSession);
                }
              }}
            >
              Điểm danh ngay
            </Button>
          </div>
        </div>
      ) : null}

      {/* Classes Section */}
      <Card
        title="Danh sách lớp đang giảng dạy"
        extra={
          <Button type="link" onClick={onNavigateClasses}>
            Xem tất cả lớp <RightOutlined />
          </Button>
        }
      >
        {classes.length === 0 ? (
          <Empty description="Bạn chưa được phân công lớp học nào tại cơ sở hiện tại." />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
            {classes.map((cls) => {
              const current = Number(cls.current_count) || 0;
              const max = Number(cls.capacity) || 1;
              const percent = Math.min(100, Math.round((current / max) * 100));

              return (
                <div key={String(cls.class_id)} className={styles.classCard} style={{ padding: 18, background: "#fff" }}>
                  <div className={styles.cardHeader}>
                    <span className={styles.className}>{String(cls.name || cls.class_id)}</span>
                    <Tag color={String(cls.status) === "dang_hoc" ? "green" : "blue"}>
                      {String(cls.status) === "dang_hoc" ? "Đang học" : String(cls.status)}
                    </Tag>
                  </div>
                  <div className={styles.courseBadge}>
                    Khóa: {String(cls.course_name || cls.course_id || "Khóa học")}
                  </div>
                  <div className={styles.infoRow}>
                    <CalendarOutlined /> Khai giảng: {String(cls.start_date || "—")}
                  </div>
                  <div className={styles.infoRow} style={{ marginTop: 8 }}>
                    <TeamOutlined /> Sĩ số: {current}/{max} học viên
                  </div>
                  <Progress percent={percent} size="small" status={percent >= 100 ? "exception" : "active"} style={{ margin: "4px 0 14px" }} />
                  <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    <Button
                      size="small"
                      type="primary"
                      onClick={() => onNavigateAttendance(cls)}
                    >
                      Vào điểm danh
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
