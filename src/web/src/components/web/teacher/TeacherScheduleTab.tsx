"use client";

import { useMemo, useState } from "react";
import { Alert, Button, Card, Empty, Segmented, Space, Table, Tag, Typography } from "antd";
import { CalendarOutlined, CheckCircleOutlined, ClockCircleOutlined, EnvironmentOutlined } from "@ant-design/icons";
import type { TeacherScheduleRow } from "@/lib/api/academics";

type Filter = "upcoming" | "today" | "all";

type Props = {
  schedule: TeacherScheduleRow[];
  loading: boolean;
  error: string;
  onOpenAttendance: (row: TeacherScheduleRow) => void;
};

const WEEKDAYS = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
const ACCENT = "#175245";

/** Business dates are Vietnam local dates, independent of the browser time zone. */
function todayInVietnam(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date());
}

function formatDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value;
  const weekday = WEEKDAYS[new Date(Date.UTC(year, month - 1, day)).getUTCDay()];
  return `${weekday}, ${String(day).padStart(2, "0")}/${String(month).padStart(2, "0")}/${year}`;
}

const hhmm = (value: string) => String(value || "").slice(0, 5);

function statusTag(status: string) {
  if (status === "da_hoc") return <Tag>Đã dạy</Tag>;
  if (status === "nghi") return <Tag color="error">Nghỉ</Tag>;
  if (status === "doi_lich") return <Tag color="warning">Đổi lịch</Tag>;
  return <Tag color="processing">Dự kiến</Tag>;
}

export function TeacherScheduleTab({ schedule, loading, error, onOpenAttendance }: Props) {
  const [filter, setFilter] = useState<Filter>("upcoming");
  const today = todayInVietnam();

  const rows = useMemo(() => {
    if (filter === "today") return schedule.filter((row) => row.date === today);
    if (filter === "upcoming") return schedule.filter((row) => row.date >= today);
    return schedule;
  }, [filter, schedule, today]);
  const todayCount = schedule.filter((row) => row.date === today).length;

  const columns = [
    {
      title: "Ngày dạy",
      dataIndex: "date",
      key: "date",
      width: 170,
      render: (value: string) => (
        <Space>
          <CalendarOutlined style={{ color: ACCENT }} />
          <span style={{ fontWeight: value === today ? 700 : 400 }}>{formatDate(value)}</span>
          {value === today && <Tag color="green">Hôm nay</Tag>}
        </Space>
      ),
    },
    {
      title: "Thời gian",
      key: "time",
      width: 130,
      render: (_: unknown, row: TeacherScheduleRow) => (
        <Space>
          <ClockCircleOutlined style={{ color: ACCENT }} />
          <span>{hhmm(row.start_time)} – {hhmm(row.end_time)}</span>
        </Space>
      ),
    },
    {
      title: "Lớp học",
      key: "class",
      render: (_: unknown, row: TeacherScheduleRow) => (
        <div>
          <strong>{row.class_name}</strong>
          <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{row.course_name} · Buổi {row.session_number}</Typography.Text></div>
        </div>
      ),
    },
    {
      title: "Phòng",
      dataIndex: "room_name",
      key: "room_name",
      width: 170,
      render: (value: string | null) => (
        <Space>
          <EnvironmentOutlined style={{ color: ACCENT }} />
          <span>{value || "Chưa xếp phòng"}</span>
        </Space>
      ),
    },
    { title: "Trạng thái", dataIndex: "status", key: "status", width: 110, render: (value: string) => statusTag(value) },
    {
      title: "",
      key: "action",
      width: 120,
      render: (_: unknown, row: TeacherScheduleRow) => (
        <Button size="small" icon={<CheckCircleOutlined />} onClick={() => onOpenAttendance(row)}>
          {row.can_edit_attendance ? "Điểm danh" : "Xem"}
        </Button>
      ),
    },
  ];

  return (
    <Card
      title={<Space><CalendarOutlined style={{ color: ACCENT }} /><span>Thời khóa biểu giảng dạy</span></Space>}
      extra={
        <Segmented<Filter>
          value={filter}
          onChange={setFilter}
          options={[
            { label: `Hôm nay (${todayCount})`, value: "today" },
            { label: "Sắp tới", value: "upcoming" },
            { label: `Tất cả (${schedule.length})`, value: "all" },
          ]}
        />
      }
    >
      {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
      {!loading && rows.length === 0 ? (
        <Empty
          description={
            schedule.length === 0
              ? "Chưa có buổi dạy nào được lên lịch cho các lớp bạn phụ trách."
              : filter === "today" ? "Hôm nay bạn không có buổi dạy." : "Không có buổi dạy sắp tới."
          }
        />
      ) : (
        <Table
          rowKey="session_id"
          dataSource={rows}
          columns={columns}
          loading={loading}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          scroll={{ x: 860 }}
        />
      )}
    </Card>
  );
}
