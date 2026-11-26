"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Avatar,
  Button,
  Card,
  message,
  Spin,
  Tabs,
  Tag,
} from "antd";
import {
  CalendarOutlined,
  CheckCircleOutlined,
  DashboardOutlined,
  EditOutlined,
  LogoutOutlined,
  ReadOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { academicsApi, type ApiRow, type SessionRow, type TeacherScheduleRow } from "@/lib/api/academics";
import { asRows } from "@/components/shared/ApiPage";
import { RequireSession, useSession } from "@/lib/auth/session";
import { TeacherOverviewTab } from "@/components/web/teacher/TeacherOverviewTab";
import { TeacherClassesTab } from "@/components/web/teacher/TeacherClassesTab";
import { TeacherAttendanceTab } from "@/components/web/teacher/TeacherAttendanceTab";
import { TeacherGradesTab } from "@/components/web/teacher/TeacherGradesTab";
import { TeacherAccountTab } from "@/components/web/teacher/TeacherAccountTab";
import { TeacherScheduleTab } from "@/components/web/teacher/TeacherScheduleTab";
import styles from "@/components/web/teacher/TeacherPortal.module.scss";

export default function TeacherRoute() {
  return (
    <RequireSession roles={["giao_vien"]}>
      <TeacherPortal />
    </RequireSession>
  );
}

function TeacherPortal() {
  const { user, signOut } = useSession();

  // Tab navigation state
  const [activeTabKey, setActiveTabKey] = useState("overview");

  // Core data states
  const [classes, setClasses] = useState<ApiRow[]>([]);
  const [activeClass, setActiveClass] = useState<ApiRow | null>(null);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [activeSession, setActiveSession] = useState<SessionRow | null>(null);
  const [roster, setRoster] = useState<ApiRow[]>([]);
  const [attendanceEditable, setAttendanceEditable] = useState(false);
  const [attendanceMap, setAttendanceMap] = useState<Record<string, { status?: string; note?: string }>>({});

  // Grade modal state
  const [selectedStudentForGrade, setSelectedStudentForGrade] = useState<ApiRow | null>(null);

  // Loading states
  const [loading, setLoading] = useState(true);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingAttendance, setLoadingAttendance] = useState(false);
  const [error, setError] = useState("");
  const [schedule, setSchedule] = useState<TeacherScheduleRow[]>([]);
  const [loadingSchedule, setLoadingSchedule] = useState(true);
  const [scheduleError, setScheduleError] = useState("");

  const loadAttendanceForSession = useCallback(async (sessionId: string) => {
    setLoadingAttendance(true);
    try {
      const result = await academicsApi.attendance(sessionId);
      const rows = asRows(result.results);
      setRoster(rows);
      setAttendanceEditable(result.can_edit_attendance === true);

      // Pre-fill attendance map
      const map: Record<string, { status?: string; note?: string }> = {};
      for (const item of rows) {
        map[String(item.enrollment_id)] = {
          status: typeof item.attendance_status === "string" ? item.attendance_status : undefined,
          note: typeof item.note === "string" ? item.note : "",
        };
      }
      setAttendanceMap(map);
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Lỗi tải thông tin điểm danh.");
    } finally {
      setLoadingAttendance(false);
    }
  }, []);

  const loadSessionsForClass = useCallback(async (classId: string, preferredSessionId?: string) => {
    setLoadingSessions(true);
    try {
      const res = await academicsApi.teacherSessions(classId);
      const sessionRows = (res.results || []) as SessionRow[];
      setSessions(sessionRows);

      if (sessionRows.length > 0) {
        // Pick the requested session (e.g. from the schedule), otherwise the first one
        const firstSess = sessionRows.find((row) => String(row.session_id) === preferredSessionId) ?? sessionRows[0];
        setActiveSession(firstSess);
        void loadAttendanceForSession(String(firstSess.session_id));
      } else {
        setActiveSession(null);
        setRoster([]);
      }
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Lỗi tải danh sách buổi học.");
    } finally {
      setLoadingSessions(false);
    }
  }, [loadAttendanceForSession]);

  // Load teacher's assigned classes
  const loadClasses = useCallback(async () => {
    setLoading(true);
    try {
      const result = await academicsApi.teacherClasses();
      const classRows = result.results || [];
      setClasses(classRows);
      setError("");

      if (classRows.length > 0) {
        // Automatically select the first class if none is selected
        const first = classRows[0];
        setActiveClass(first);
        void loadSessionsForClass(String(first.class_id));
      } else {
        setActiveClass(null);
        setSessions([]);
        setActiveSession(null);
        setRoster([]);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể tải danh sách lớp học.");
    } finally {
      setLoading(false);
    }
  }, [loadSessionsForClass]);

  const loadSchedule = useCallback(async () => {
    setLoadingSchedule(true);
    try {
      const result = await academicsApi.teacherSchedule();
      setSchedule(result.results || []);
      setScheduleError("");
    } catch (reason) {
      setScheduleError(reason instanceof Error ? reason.message : "Không tải được thời khóa biểu.");
    } finally {
      setLoadingSchedule(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) {
        void loadClasses();
        void loadSchedule();
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadClasses, loadSchedule]);

  // Handler when user selects another class
  const handleSelectClass = (cls: ApiRow) => {
    setActiveClass(cls);
    void loadSessionsForClass(String(cls.class_id));
  };

  // Handler when user selects another session
  const handleSelectSession = (session: SessionRow) => {
    setActiveSession(session);
    void loadAttendanceForSession(String(session.session_id));
  };

  // Navigate shortcut from overview
  const handleNavigateAttendance = (cls: ApiRow, sess?: SessionRow) => {
    setActiveClass(cls);
    // Reload the class's sessions so the session list matches the selected class.
    void loadSessionsForClass(String(cls.class_id), sess ? String(sess.session_id) : undefined);
    setActiveTabKey("attendance");
  };

  const handleOpenScheduleAttendance = (row: TeacherScheduleRow) => {
    const cls = classes.find((item) => String(item.class_id) === row.class_id)
      ?? { class_id: row.class_id, name: row.class_name, course_name: row.course_name };
    setActiveClass(cls);
    void loadSessionsForClass(row.class_id, row.session_id);
    setActiveTabKey("attendance");
  };

  // Find next upcoming session for display in overview
  const nextSession = sessions.find((s) => String(s.status) !== "da_hoc") || (sessions.length > 0 ? sessions[0] : null);

  const tabItems = [
    {
      key: "overview",
      label: (
        <span>
          <DashboardOutlined /> Tổng quan
        </span>
      ),
      children: (
        <TeacherOverviewTab
          classes={classes}
          sessions={sessions}
          nextSession={nextSession}
          siteCode={user?.site_code ?? null}
          onNavigateAttendance={handleNavigateAttendance}
          onNavigateClasses={() => setActiveTabKey("classes")}
        />
      ),
    },
    {
      key: "classes",
      label: (
        <span>
          <ReadOutlined /> Lớp được giao
        </span>
      ),
      children: (
        <TeacherClassesTab
          classes={classes}
          activeClass={activeClass}
          sessions={sessions}
          roster={roster}
          loadingSessions={loadingSessions}
          onSelectClass={handleSelectClass}
          onSelectSessionForAttendance={(s) => {
            setActiveSession(s);
            void loadAttendanceForSession(String(s.session_id));
            setActiveTabKey("attendance");
          }}
          onSelectStudentForGrade={(s) => {
            setSelectedStudentForGrade(s);
            setActiveTabKey("grades");
          }}
        />
      ),
    },
    {
      key: "schedule",
      label: (
        <span>
          <CalendarOutlined /> Thời khóa biểu ({schedule.length})
        </span>
      ),
      children: (
        <TeacherScheduleTab
          schedule={schedule}
          loading={loadingSchedule}
          error={scheduleError}
          onOpenAttendance={handleOpenScheduleAttendance}
        />
      ),
    },
    {
      key: "attendance",
      label: (
        <span>
          <CheckCircleOutlined /> Điểm danh
        </span>
      ),
      children: (
        <TeacherAttendanceTab
          classes={classes}
          activeClass={activeClass}
          sessions={sessions}
          activeSession={activeSession}
          roster={roster}
          attendanceEditable={attendanceEditable}
          attendanceMap={attendanceMap}
          loadingSession={loadingAttendance}
          onSelectClass={handleSelectClass}
          onSelectSession={handleSelectSession}
          onAttendanceMapChange={setAttendanceMap}
          onRefreshSession={() => {
            if (activeSession) void loadAttendanceForSession(String(activeSession.session_id));
          }}
        />
      ),
    },
    {
      key: "grades",
      label: (
        <span>
          <EditOutlined /> Quản lý điểm
        </span>
      ),
      children: (
        <TeacherGradesTab
          classes={classes}
          activeClass={activeClass}
          roster={roster}
          selectedStudent={selectedStudentForGrade}
          onSelectClass={handleSelectClass}
          onCloseStudentModal={() => setSelectedStudentForGrade(null)}
          onOpenStudentModal={setSelectedStudentForGrade}
        />
      ),
    },
    {
      key: "account",
      label: (
        <span>
          <SafetyCertificateOutlined /> Hồ sơ & Bảo mật
        </span>
      ),
      children: <TeacherAccountTab />,
    },
  ];

  const headerButtonStyle = { background: "rgba(255,255,255,0.15)", color: "#fff", borderColor: "rgba(255,255,255,0.3)" };

  return (
    <main className={styles.portalContainer}>
      {/* Teacher Workspace Header */}
      <div className={styles.portalHeader}>
        <div className={styles.teacherInfo}>
          <Avatar size={54} className={styles.avatar} src={user?.avatar_secure_url || undefined} icon={<UserOutlined />}>
            {user?.username ? user.username.slice(0, 2).toUpperCase() : "GV"}
          </Avatar>
          <div className={styles.meta}>
            <h2>Không gian Giáo viên</h2>
            <p>
              <span>Xin chào, <strong>{user?.username || "Giáo viên"}</strong></span>
              <span>·</span>
              <Tag color="green">Mã GV: {user?.profile_id || "Chưa xác định"}</Tag>
              <Tag color="cyan">Cơ sở: {user?.site_code || "Chưa xác định"}</Tag>
            </p>
          </div>
        </div>

        <div className={styles.actions}>
          <Button
            icon={<ReloadOutlined />}
            style={headerButtonStyle}
            onClick={() => {
              void loadClasses();
              void loadSchedule();
            }}
          >
            Làm mới
          </Button>
          <Button
            icon={<SafetyCertificateOutlined />}
            style={headerButtonStyle}
            onClick={() => setActiveTabKey("account")}
          >
            Đổi mật khẩu
          </Button>
          <Button
            danger
            icon={<LogoutOutlined />}
            onClick={async () => {
              try {
                await signOut();
              } catch {
                message.error("Không thu hồi được phiên đăng nhập.");
              }
            }}
          >
            Đăng xuất
          </Button>
        </div>
      </div>

      {error && (
        <Alert
          type="error"
          showIcon
          title="Không thể tải dữ liệu"
          description={error}
          style={{ marginBottom: 20 }}
        />
      )}

      <Card styles={{ body: { padding: "12px 24px 24px" } }} style={{ borderRadius: 16, boxShadow: "0 4px 16px rgba(0,0,0,0.04)" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: "60px 0" }}>
            <Spin size="large" description="Đang kết nối CSDL và tải lớp học..." />
          </div>
        ) : (
          <Tabs
            activeKey={activeTabKey}
            onChange={setActiveTabKey}
            items={tabItems}
            size="large"
          />
        )}
      </Card>
    </main>
  );
}
