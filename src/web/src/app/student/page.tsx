"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Avatar, Button, Card, Spin, Tabs, Tag, Typography, message } from "antd";
import {
  LogoutOutlined,
  UserOutlined,
  DashboardOutlined,
  BookOutlined,
  CalendarOutlined,
  DollarCircleOutlined,
  TrophyOutlined,
  SettingOutlined,
  LockOutlined,
  SyncOutlined
} from "@ant-design/icons";
import { academicsApi, type ApiRow } from "@/lib/api/academics";
import { RequireSession, useSession } from "@/lib/auth/session";
import { StudentOverviewTab } from "@/components/web/student/StudentOverviewTab";
import { StudentCoursesTab } from "@/components/web/student/StudentCoursesTab";
import { StudentScheduleTab } from "@/components/web/student/StudentScheduleTab";
import { StudentGradesTab } from "@/components/web/student/StudentGradesTab";
import { StudentAccountTab } from "@/components/web/student/StudentAccountTab";
import { StudentTuitionPanel } from "@/components/web/student/StudentTuitionPanel";
import styles from "@/components/web/student/StudentPortal.module.scss";

type PortalData = {
  profile: ApiRow | null;
  enrollments: ApiRow[];
  schedule: ApiRow[];
  tuition: ApiRow[];
  grades: ApiRow[];
};

export default function StudentRoute() {
  return (
    <RequireSession roles={["hoc_vien"]}>
      <StudentPortal />
    </RequireSession>
  );
}

function StudentPortal() {
  const { user, signOut } = useSession();
  const [data, setData] = useState<PortalData>({
    profile: null,
    enrollments: [],
    schedule: [],
    tuition: [],
    grades: [],
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [returnAttemptId, setReturnAttemptId] = useState<string | null>(null);

  // SePay redirects back with ?payment=<attempt>; open the tuition tab and confirm via the API.
  useEffect(() => {
    const attempt = new URLSearchParams(window.location.search).get("payment");
    if (!attempt || !/^[A-Za-z0-9_-]{1,24}$/.test(attempt)) return;
    queueMicrotask(() => {
      setReturnAttemptId(attempt);
      setActiveTab("tuition");
    });
    window.history.replaceState(null, "", window.location.pathname);
  }, []);
  const clearReturnAttempt = useCallback(() => setReturnAttemptId(null), []);

  const load = useCallback(async (isRefresh = false) => {
    if (!user) return;
    if (isRefresh) setRefreshing(true);
    try {
      const results = await Promise.allSettled([
        academicsApi.studentProfile(user.slug),
        academicsApi.studentEnrollments(user.slug),
        academicsApi.studentSchedule(user.slug),
        academicsApi.studentTuition(user.slug),
        academicsApi.studentGrades(user.slug),
      ]);

      const failures = results
        .filter((item) => item.status === "rejected")
        .map((item) => (item.status === "rejected" && item.reason instanceof Error ? item.reason.message : "API lỗi"));

      if (failures.length > 0) {
        setError(failures.join(" · "));
      } else {
        setError("");
      }

      setData({
        profile: results[0].status === "fulfilled" ? results[0].value : null,
        enrollments: results[1].status === "fulfilled" ? results[1].value.results : [],
        schedule: results[2].status === "fulfilled" ? results[2].value.results : [],
        tuition: results[3].status === "fulfilled" ? results[3].value.results : [],
        grades: results[4].status === "fulfilled" ? results[4].value.results : [],
      });
    } catch {
      setError("Không thể tải thông tin học viên.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) void load();
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const refreshAll = useCallback(() => load(true), [load]);

  const handleLogout = async () => {
    try {
      await signOut();
    } catch {
      message.error("Không thu hồi được phiên đăng nhập.");
    }
  };

  const studentName = String(data.profile?.full_name || user?.username || "Học viên");
  const studentId = String(data.profile?.student_id || user?.account_id || "");
  const siteCode = String(data.profile?.site_code || user?.site_code || "TD");

  return (
    <main className={styles.portalContainer}>
      {/* 1. Portal Header */}
      <div className={styles.portalHeader}>
        <div className={styles.studentInfo}>
          <Avatar size={54} icon={<UserOutlined />} className={styles.avatar} />
          <div className={styles.meta}>
            <h2>{studentName}</h2>
            <p>
              Mã HV: <strong>{studentId}</strong> · Cơ sở: <Tag color="cyan">{siteCode}</Tag> · Trạng thái: <Tag color="green">Đang theo học</Tag>
            </p>
          </div>
        </div>

        <div className={styles.actions}>
          <Button
            icon={<SyncOutlined spin={refreshing} />}
            onClick={() => void load(true)}
            style={{ background: "rgba(255,255,255,0.15)", color: "#fff", borderColor: "rgba(255,255,255,0.3)" }}
          >
            Làm mới
          </Button>
          <Button
            icon={<LockOutlined />}
            onClick={() => setActiveTab("profile")}
            style={{ background: "rgba(255,255,255,0.15)", color: "#fff", borderColor: "rgba(255,255,255,0.3)" }}
          >
            Đổi mật khẩu
          </Button>
          <Button danger icon={<LogoutOutlined />} onClick={handleLogout}>
            Đăng xuất
          </Button>
        </div>
      </div>

      {/* 2. Cảnh báo đổi mật khẩu lần đầu */}
      {user?.must_change_password && (
        <Alert
          className={styles.passwordBanner}
          type="warning"
          showIcon
          title="Tài khoản đang dùng mật khẩu tạm do trung tâm cấp"
          description="Để bảo đảm an toàn thông tin cá nhân và kết quả học tập, bạn nên đổi sang mật khẩu riêng."
          action={
            <Button size="small" type="primary" onClick={() => setActiveTab("profile")}>
              Đổi mật khẩu ngay
            </Button>
          }
        />
      )}

      {/* 3. Lỗi kết nối nếu có */}
      {error && <Alert type="error" showIcon title="Một số dữ liệu chưa tải được" description={error} style={{ marginBottom: 16 }} />}

      {/* 4. Nội dung các Tab chức năng */}
      <Card bodyStyle={{ padding: "12px 24px 24px" }} style={{ borderRadius: 16, boxShadow: "0 4px 16px rgba(0,0,0,0.04)" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <Spin size="large" description="Đang tải dữ liệu học tập..." />
          </div>
        ) : (
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            size="large"
            items={[
              {
                key: "overview",
                label: (
                  <span>
                    <DashboardOutlined /> Tổng quan học tập
                  </span>
                ),
                children: (
                  <StudentOverviewTab
                    profile={data.profile}
                    enrollments={data.enrollments}
                    schedule={data.schedule}
                    tuition={data.tuition}
                    grades={data.grades}
                    onSelectTab={setActiveTab}
                  />
                ),
              },
              {
                key: "courses",
                label: (
                  <span>
                    <BookOutlined /> Lớp học của tôi ({data.enrollments.length})
                  </span>
                ),
                children: (
                  <StudentCoursesTab
                    enrollments={data.enrollments}
                    loading={loading}
                    onSelectTab={setActiveTab}
                  />
                ),
              },
              {
                key: "schedule",
                label: (
                  <span>
                    <CalendarOutlined /> Thời khóa biểu ({data.schedule.length})
                  </span>
                ),
                children: (
                  <StudentScheduleTab
                    schedule={data.schedule}
                    loading={loading}
                  />
                ),
              },
              {
                key: "tuition",
                label: (
                  <span>
                    <DollarCircleOutlined /> Học phí & Biên lai ({data.tuition.length})
                  </span>
                ),
                children: (
                  <StudentTuitionPanel
                    rows={data.tuition}
                    loading={loading}
                    slug={user?.slug || ""}
                    onRefresh={refreshAll}
                    returnAttemptId={returnAttemptId}
                    onReturnHandled={clearReturnAttempt}
                  />
                ),
              },
              {
                key: "grades",
                label: (
                  <span>
                    <TrophyOutlined /> Kết quả học tập ({data.grades.length})
                  </span>
                ),
                children: (
                  <StudentGradesTab
                    grades={data.grades}
                    loading={loading}
                  />
                ),
              },
              {
                key: "profile",
                label: (
                  <span>
                    <SettingOutlined /> Hồ sơ & Bảo mật
                  </span>
                ),
                children: (
                  <StudentAccountTab
                    profile={data.profile}
                    slug={user?.slug || ""}
                    onRefresh={() => load(true)}
                  />
                ),
              },
            ]}
          />
        )}
      </Card>
    </main>
  );
}
