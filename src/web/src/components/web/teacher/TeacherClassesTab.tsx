"use client";

import { Card, Table, Tag, Button, Space, Typography, Row, Col, Empty, Badge } from "antd";
import {
  CalendarOutlined,
  CheckCircleOutlined,
  EditOutlined,
  InfoCircleOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import type { ApiRow, SessionRow } from "@/lib/api/academics";
import styles from "./TeacherPortal.module.scss";

type TeacherClassesTabProps = {
  classes: ApiRow[];
  activeClass: ApiRow | null;
  sessions: SessionRow[];
  roster: ApiRow[];
  loadingSessions: boolean;
  onSelectClass: (cls: ApiRow) => void;
  onSelectSessionForAttendance: (session: SessionRow) => void;
  onSelectStudentForGrade: (student: ApiRow) => void;
};

export function TeacherClassesTab({
  classes,
  activeClass,
  sessions,
  roster,
  loadingSessions,
  onSelectClass,
  onSelectSessionForAttendance,
  onSelectStudentForGrade,
}: TeacherClassesTabProps) {
  const sessionColumns = [
    {
      title: "Buổi",
      dataIndex: "sequence",
      key: "sequence",
      width: 70,
      render: (seq: unknown, row: SessionRow) => (
        <span style={{ fontWeight: 600 }}>
          #{String(seq || row.session_number || "")}
        </span>
      ),
    },
    {
      title: "Ngày học",
      dataIndex: "session_date",
      key: "session_date",
      render: (val: unknown, row: SessionRow) => String(val || row.date || "—"),
    },
    {
      title: "Thời gian",
      key: "time",
      render: (_: unknown, row: SessionRow) => (
        <span>{`${String(row.start_time || "")} – ${String(row.end_time || "")}`}</span>
      ),
    },
    {
      title: "Phòng học",
      dataIndex: "room_name",
      key: "room_name",
      render: (val: unknown) => String(val || "Chưa xếp phòng"),
    },
    {
      title: "Trạng thái",
      dataIndex: "status",
      key: "status",
      render: (val: unknown) => {
        const s = String(val);
        if (s === "da_hoc") return <Tag color="green">Đã học</Tag>;
        if (s === "du_kien") return <Tag color="blue">Dự kiến</Tag>;
        if (s === "dang_dien_ra") return <Tag color="orange">Đang diễn ra</Tag>;
        if (s === "huy") return <Tag color="red">Hủy</Tag>;
        return <Tag>{s}</Tag>;
      },
    },
    {
      title: "Thao tác",
      key: "action",
      render: (_: unknown, row: SessionRow) => (
        <Button
          type="primary"
          size="small"
          icon={<CheckCircleOutlined />}
          onClick={() => onSelectSessionForAttendance(row)}
        >
          Điểm danh
        </Button>
      ),
    },
  ];

  const rosterColumns = [
    {
      title: "Mã học viên",
      dataIndex: "student_id",
      key: "student_id",
      render: (val: unknown) => <Tag color="geekblue">{String(val || "—")}</Tag>,
    },
    {
      title: "Họ và tên",
      dataIndex: "student_name",
      key: "student_name",
      render: (val: unknown) => <strong>{String(val || "—")}</strong>,
    },
    {
      title: "Mã đăng ký",
      dataIndex: "enrollment_id",
      key: "enrollment_id",
      render: (val: unknown) => <span style={{ color: "#64748b" }}>{String(val || "—")}</span>,
    },
    {
      title: "Trạng thái học",
      dataIndex: "enrollment_status",
      key: "enrollment_status",
      render: (val: unknown) => {
        const s = String(val);
        if (s === "dang_hoc") return <Badge status="success" text="Đang học" />;
        if (s === "da_hoan_thanh") return <Badge status="default" text="Hoàn thành" />;
        if (s === "da_chuyen_di") return <Badge status="warning" text="Đã chuyển đi" />;
        return <Badge status="processing" text={s} />;
      },
    },
    {
      title: "Hành động",
      key: "action",
      render: (_: unknown, row: ApiRow) => (
        <Button
          size="small"
          icon={<EditOutlined />}
          onClick={() => onSelectStudentForGrade(row)}
        >
          Nhập / Xem điểm
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={[16, 16]}>
        {/* Classes List */}
        <Col xs={24} md={8}>
          <Card title="Danh sách lớp học" styles={{ body: { padding: "12px 16px" } }}>
            {classes.length === 0 ? (
              <Empty description="Chưa có lớp nào được phân công." />
            ) : (
              <Space direction="vertical" style={{ width: "100%" }} size={12}>
                {classes.map((cls) => {
                  const isSelected = activeClass && String(activeClass.class_id) === String(cls.class_id);
                  return (
                    <div
                      key={String(cls.class_id)}
                      onClick={() => onSelectClass(cls)}
                      style={{
                        padding: 14,
                        borderRadius: 10,
                        border: isSelected ? "2px solid #3b82f6" : "1px solid #e2e8f0",
                        background: isSelected ? "#eff6ff" : "#fff",
                        cursor: "pointer",
                        transition: "all 0.2s",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontWeight: 700, fontSize: 15, color: isSelected ? "#1d4ed8" : "#1e293b" }}>
                          {String(cls.name || cls.class_id)}
                        </span>
                        <Tag color={String(cls.status) === "dang_hoc" ? "green" : "default"}>
                          {String(cls.status) === "dang_hoc" ? "Đang học" : String(cls.status)}
                        </Tag>
                      </div>
                      <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>
                        Khóa: {String(cls.course_name || cls.course_id || "")}
                      </div>
                      <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
                        Sĩ số: {String(cls.current_count || 0)} / {String(cls.capacity || 0)} học viên
                      </div>
                    </div>
                  );
                })}
              </Space>
            )}
          </Card>
        </Col>

        {/* Selected Class Details */}
        <Col xs={24} md={16}>
          {activeClass ? (
            <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
              {/* Header Info */}
              <Card>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
                  <div>
                    <Typography.Title level={4} style={{ margin: 0, color: "#1e293b" }}>
                      {String(activeClass.name || activeClass.class_id)}
                    </Typography.Title>
                    <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                      Khóa đào tạo: <strong>{String(activeClass.course_name || activeClass.course_id)}</strong> · Cơ sở: {String(activeClass.site_code || "TD")}
                    </Typography.Text>
                  </div>
                  <Tag color="cyan" style={{ fontSize: 13, padding: "4px 10px" }}>
                    Thời gian: {String(activeClass.start_date || "")} → {String(activeClass.end_date || "Đang học")}
                  </Tag>
                </div>
              </Card>

              {/* Sessions Table */}
              <Card
                title={
                  <span>
                    <CalendarOutlined style={{ marginRight: 8, color: "#3b82f6" }} />
                    Danh sách buổi học ({sessions.length})
                  </span>
                }
              >
                <Table
                  rowKey={(row) => String(row.session_id)}
                  dataSource={sessions}
                  columns={sessionColumns}
                  loading={loadingSessions}
                  pagination={{ pageSize: 6 }}
                  scroll={{ x: 650 }}
                  size="small"
                />
              </Card>

              {/* Roster Table */}
              <Card
                title={
                  <span>
                    <TeamOutlined style={{ marginRight: 8, color: "#10b981" }} />
                    Học viên trong lớp ({roster.length})
                  </span>
                }
              >
                {roster.length === 0 ? (
                  <Empty description="Chọn một buổi học hoặc lớp học để xem danh sách học viên." image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  <Table
                    rowKey={(row) => String(row.enrollment_id)}
                    dataSource={roster}
                    columns={rosterColumns}
                    pagination={false}
                    scroll={{ x: 650 }}
                    size="small"
                  />
                )}
              </Card>
            </Space>
          ) : (
            <Card>
              <Empty
                image={<InfoCircleOutlined style={{ fontSize: 48, color: "#94a3b8" }} />}
                description="Vui lòng chọn một lớp học ở danh sách bên trái để xem lịch học và danh sách học viên."
              />
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
}
