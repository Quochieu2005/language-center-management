"use client";

import { Card, Table, Tag, Typography, Empty, Space } from "antd";
import { CalendarOutlined, ClockCircleOutlined, EnvironmentOutlined, UserOutlined } from "@ant-design/icons";
import type { ApiRow } from "@/lib/api/academics";

type Props = {
  schedule: ApiRow[];
  loading: boolean;
};

export function StudentScheduleTab({ schedule, loading }: Props) {
  if (schedule.length === 0) {
    return (
      <Card>
        <Empty description="Chưa có lịch học hoặc buổi học nào được lên kế hoạch." />
      </Card>
    );
  }

  const columns = [
    {
      title: "Buổi số",
      dataIndex: "session_number",
      key: "session_number",
      width: 90,
      render: (val: unknown) => <Tag color="blue">Buổi {String(val || 1)}</Tag>,
    },
    {
      title: "Lớp học",
      dataIndex: "class_name",
      key: "class_name",
      render: (val: unknown) => <strong>{String(val || "---")}</strong>,
    },
    {
      title: "Ngày học",
      dataIndex: "date",
      key: "date",
      render: (val: unknown) => (
        <Space>
          <CalendarOutlined style={{ color: "#175245" }} />
          <span>{String(val || "---")}</span>
        </Space>
      ),
    },
    {
      title: "Thời gian",
      key: "time",
      render: (_: unknown, row: ApiRow) => (
        <Space>
          <ClockCircleOutlined style={{ color: "#fa8c16" }} />
          <span>{String(row.start_time || "")} - {String(row.end_time || "")}</span>
        </Space>
      ),
    },
    {
      title: "Phòng học",
      dataIndex: "room_name",
      key: "room_name",
      render: (val: unknown) => (
        <Space>
          <EnvironmentOutlined style={{ color: "#52c41a" }} />
          <span>{String(val || "Chưa xếp phòng")}</span>
        </Space>
      ),
    },
    {
      title: "Giảng viên",
      dataIndex: "teacher_name",
      key: "teacher_name",
      render: (val: unknown) => (
        <Space>
          <UserOutlined />
          <span>{String(val || "---")}</span>
        </Space>
      ),
    },
    {
      title: "Trạng thái",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (val: unknown) => {
        const s = String(val || "").toLowerCase();
        if (s === "da_hoc") return <Tag color="default">Đã hoàn thành</Tag>;
        if (s === "nghi") return <Tag color="error">Nghỉ học</Tag>;
        if (s === "doi_lich") return <Tag color="warning">Đổi lịch</Tag>;
        return <Tag color="processing">Sắp diễn ra</Tag>;
      },
    },
    {
      title: "Nội dung / Ghi chú",
      dataIndex: "ghi_chu",
      key: "ghi_chu",
      render: (val: unknown) => (
        <Typography.Text type="secondary">
          {String(val || "Bài học theo giáo trình")}
        </Typography.Text>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <CalendarOutlined style={{ color: "#175245" }} />
          <span>Thời khóa biểu & Lịch học ({schedule.length} buổi)</span>
        </Space>
      }
    >
      <Table
        rowKey={(row) => String(row.session_id || Math.random())}
        dataSource={schedule}
        columns={columns}
        loading={loading}
        pagination={{ pageSize: 10 }}
        scroll={{ x: 800 }}
      />
    </Card>
  );
}
