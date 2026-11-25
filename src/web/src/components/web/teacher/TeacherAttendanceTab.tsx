"use client";

import { useState } from "react";
import {
  Card,
  Table,
  Select,
  Button,
  Input,
  Tag,
  Alert,
  Space,
  Row,
  Col,
  Typography,
  message,
  Empty,
  Popconfirm,
} from "antd";
import {
  CheckCircleOutlined,
  SaveOutlined,
  ReloadOutlined,
  ExclamationCircleOutlined,
  CheckOutlined,
  CalendarOutlined,
} from "@ant-design/icons";
import { academicsApi, type ApiRow, type SessionRow } from "@/lib/api/academics";
import styles from "./TeacherPortal.module.scss";

type TeacherAttendanceTabProps = {
  classes: ApiRow[];
  activeClass: ApiRow | null;
  sessions: SessionRow[];
  activeSession: SessionRow | null;
  roster: ApiRow[];
  attendanceEditable: boolean;
  attendanceMap: Record<string, { status?: string; note?: string }>;
  loadingSession: boolean;
  onSelectClass: (cls: ApiRow) => void;
  onSelectSession: (session: SessionRow) => void;
  onAttendanceMapChange: (map: Record<string, { status?: string; note?: string }>) => void;
  onRefreshSession: () => void;
};

const attendanceOptions = [
  { value: "co_mat", label: "Có mặt", color: "green" },
  { value: "tre", label: "Đi trễ", color: "gold" },
  { value: "vang_co_phep", label: "Vắng có phép", color: "blue" },
  { value: "vang_khong_phep", label: "Vắng không phép", color: "red" },
];

export function TeacherAttendanceTab({
  classes,
  activeClass,
  sessions,
  activeSession,
  roster,
  attendanceEditable,
  attendanceMap,
  loadingSession,
  onSelectClass,
  onSelectSession,
  onAttendanceMapChange,
  onRefreshSession,
}: TeacherAttendanceTabProps) {
  const [saving, setSaving] = useState(false);

  // Quick action: set all students to present
  const handleMarkAllPresent = () => {
    if (!attendanceEditable || roster.length === 0) return;
    const nextMap = { ...attendanceMap };
    for (const r of roster) {
      const eid = String(r.enrollment_id);
      nextMap[eid] = {
        ...nextMap[eid],
        status: "co_mat",
        note: nextMap[eid]?.note || "",
      };
    }
    onAttendanceMapChange(nextMap);
    message.info("Đã đánh dấu tất cả học viên: Có mặt");
  };

  const handleStatusChange = (enrollmentId: string, status: string) => {
    onAttendanceMapChange({
      ...attendanceMap,
      [enrollmentId]: {
        ...attendanceMap[enrollmentId],
        status,
      },
    });
  };

  const handleNoteChange = (enrollmentId: string, note: string) => {
    onAttendanceMapChange({
      ...attendanceMap,
      [enrollmentId]: {
        ...attendanceMap[enrollmentId],
        note,
      },
    });
  };

  const handleSaveAttendance = async () => {
    if (!activeSession || !attendanceEditable) return;

    // Validation: make sure all students have attendance status
    const incomplete = roster.some((r) => !attendanceMap[String(r.enrollment_id)]?.status);
    if (incomplete) {
      message.warning("Vui lòng chọn trạng thái điểm danh cho tất cả học viên trong danh sách.");
      return;
    }

    setSaving(true);
    try {
      const items = roster.map((r) => ({
        enrollment_id: String(r.enrollment_id),
        status: (attendanceMap[String(r.enrollment_id)]?.status || "co_mat") as
          | "co_mat"
          | "tre"
          | "vang_co_phep"
          | "vang_khong_phep",
        note: attendanceMap[String(r.enrollment_id)]?.note || "",
      }));

      const res = await academicsApi.saveAttendance(String(activeSession.session_id), items);
      message.success("Đã lưu điểm danh thành công!");

      const alerts = res.email_alerts as Record<string, unknown> | undefined;
      if (alerts && Object.keys(alerts).length > 0) {
        message.info(`Đã gửi cảnh báo vắng học tới ${Object.keys(alerts).length} học viên theo quy định.`);
      }

      onRefreshSession();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Không thể lưu điểm danh.");
    } finally {
      setSaving(false);
    }
  };

  const attendanceColumns = [
    {
      title: "#",
      key: "index",
      width: 50,
      render: (_: unknown, __: unknown, idx: number) => idx + 1,
    },
    {
      title: "Học viên",
      dataIndex: "student_name",
      key: "student_name",
      render: (val: unknown, row: ApiRow) => (
        <div>
          <div style={{ fontWeight: 600, color: "#1e293b" }}>{String(val || "—")}</div>
          <div style={{ fontSize: 12, color: "#64748b" }}>Mã HV: {String(row.student_id || "")}</div>
        </div>
      ),
    },
    {
      title: "Mã đăng ký",
      dataIndex: "enrollment_id",
      key: "enrollment_id",
      width: 140,
      render: (val: unknown) => <Tag>{String(val || "—")}</Tag>,
    },
    {
      title: "Trạng thái điểm danh",
      key: "attendance_status",
      width: 220,
      render: (_: unknown, row: ApiRow) => {
        const eid = String(row.enrollment_id);
        const current = attendanceMap[eid]?.status;
        return (
          <Select
            value={current}
            disabled={!attendanceEditable}
            placeholder="Chọn trạng thái"
            style={{ width: "100%" }}
            onChange={(val) => handleStatusChange(eid, val)}
            options={attendanceOptions.map((opt) => ({
              value: opt.value,
              label: (
                <span>
                  <Tag color={opt.color} style={{ marginRight: 6 }}>
                    {opt.label}
                  </Tag>
                </span>
              ),
            }))}
          />
        );
      },
    },
    {
      title: "Ghi chú buổi học",
      key: "note",
      render: (_: unknown, row: ApiRow) => {
        const eid = String(row.enrollment_id);
        const current = attendanceMap[eid]?.note || "";
        return (
          <Input
            value={current}
            disabled={!attendanceEditable}
            maxLength={500}
            placeholder="Nhập lý do vắng / ghi chú..."
            onChange={(e) => handleNoteChange(eid, e.target.value)}
          />
        );
      },
    },
  ];

  return (
    <div>
      {/* Selection Row */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={12}>
            <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
              Chọn Lớp học:
            </Typography.Text>
            <Select
              placeholder="Chọn lớp học"
              style={{ width: "100%" }}
              value={activeClass ? String(activeClass.class_id) : undefined}
              onChange={(val) => {
                const found = classes.find((c) => String(c.class_id) === val);
                if (found) onSelectClass(found);
              }}
              options={classes.map((c) => ({
                value: String(c.class_id),
                label: `${String(c.name || c.class_id)} · ${String(c.course_name || "")}`,
              }))}
            />
          </Col>
          <Col xs={24} md={12}>
            <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
              Chọn Buổi học:
            </Typography.Text>
            <Select
              placeholder={activeClass ? "Chọn buổi học" : "Chọn lớp trước"}
              disabled={!activeClass || sessions.length === 0}
              style={{ width: "100%" }}
              value={activeSession ? String(activeSession.session_id) : undefined}
              onChange={(val) => {
                const found = sessions.find((s) => String(s.session_id) === val);
                if (found) onSelectSession(found);
              }}
              options={sessions.map((s) => {
                const sRow = s as Record<string, unknown>;
                const seq = sRow.sequence ?? s.session_number ?? "";
                const sDate = sRow.session_date ?? s.date ?? "";
                return {
                  value: String(s.session_id),
                  label: `Buổi #${String(seq)} · ${String(sDate)} (${String(s.start_time || "")} - ${String(s.end_time || "")})`,
                };
              })}
            />
          </Col>
        </Row>
      </Card>

      {/* Session Attendance Sheet */}
      {activeSession ? (
        <Card
          title={
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <CalendarOutlined style={{ color: "#3b82f6", fontSize: 18 }} />
              <span>
                Điểm danh: <strong>Buổi #{String((activeSession as Record<string, unknown>).sequence ?? activeSession.session_number ?? "")}</strong> — Ngày: {String((activeSession as Record<string, unknown>).session_date ?? activeSession.date ?? "")}
              </span>
              <Tag color={String(activeSession.status) === "da_hoc" ? "green" : "blue"}>
                {String(activeSession.status) === "da_hoc" ? "Đã học" : String(activeSession.status)}
              </Tag>
            </div>
          }
          extra={
            <Space wrap>
              {attendanceEditable && (
                <Button icon={<CheckOutlined />} onClick={handleMarkAllPresent}>
                  Tất cả có mặt
                </Button>
              )}
              <Button icon={<ReloadOutlined />} onClick={onRefreshSession}>
                Làm mới
              </Button>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                disabled={!attendanceEditable}
                loading={saving}
                onClick={handleSaveAttendance}
              >
                Lưu điểm danh
              </Button>
            </Space>
          }
        >
          {!attendanceEditable && (
            <Alert
              type="info"
              showIcon
              icon={<ExclamationCircleOutlined />}
              title="Chế độ chỉ đọc"
              description="Buổi học này chỉ có thể xem điểm danh. Bạn không thể chỉnh sửa điểm danh của buổi học không do bạn trực tiếp giảng dạy."
              style={{ marginBottom: 16 }}
            />
          )}

          <Table
            rowKey={(r) => String(r.enrollment_id)}
            dataSource={roster}
            columns={attendanceColumns}
            loading={loadingSession}
            pagination={false}
            scroll={{ x: 750 }}
          />
        </Card>
      ) : (
        <Card>
          <Empty description="Vui lòng chọn lớp học và buổi học ở trên để tiến hành điểm danh học viên." />
        </Card>
      )}
    </div>
  );
}
