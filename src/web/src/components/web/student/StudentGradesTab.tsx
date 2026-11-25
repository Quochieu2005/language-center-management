"use client";

import { Card, Table, Tag, Typography, Empty, Space, Statistic, Row, Col } from "antd";
import { TrophyOutlined, StarOutlined, CheckCircleOutlined } from "@ant-design/icons";
import type { ApiRow } from "@/lib/api/academics";
import styles from "./StudentPortal.module.scss";

type Props = {
  grades: ApiRow[];
  loading: boolean;
};

const gradeTypeLabels: Record<string, string> = {
  nghe: "Kỹ năng Nghe (Listening)",
  noi: "Kỹ năng Nói (Speaking)",
  doc: "Kỹ năng Đọc (Reading)",
  viet: "Kỹ năng Viết (Writing)",
  giua_ky: "Kiểm tra Giữa kỳ (Midterm)",
  cuoi_ky: "Thi Cuối kỳ (Final)",
};

export function StudentGradesTab({ grades, loading }: Props) {
  if (grades.length === 0) {
    return (
      <Card>
        <Empty description="Chưa có kết quả điểm số nào được cập nhật." />
      </Card>
    );
  }

  // Tinh diem trung binh
  const avg = (
    grades.reduce((acc, curr) => acc + Number(curr.score || 0), 0) / grades.length
  ).toFixed(2);

  const getScoreClass = (score: number) => {
    if (score >= 8.0) return styles.high;
    if (score >= 6.5) return styles.medium;
    return styles.low;
  };

  const columns = [
    {
      title: "Lớp học",
      dataIndex: "class_name",
      key: "class_name",
      render: (val: unknown) => <strong>{String(val || "Lớp học")}</strong>,
    },
    {
      title: "Hạng mục điểm",
      dataIndex: "grade_type",
      key: "grade_type",
      render: (val: unknown) => {
        const key = String(val || "").toLowerCase();
        return <span>{gradeTypeLabels[key] || String(val)}</span>;
      },
    },
    {
      title: "Điểm số (Thang 10)",
      dataIndex: "score",
      key: "score",
      width: 180,
      render: (val: unknown) => {
        const num = Number(val || 0);
        return (
          <span className={`${styles.gradeScoreBox} ${getScoreClass(num)}`}>
            {num.toFixed(1)} / 10
          </span>
        );
      },
    },
    {
      title: "Đánh giá xếp loại",
      key: "evaluation",
      render: (_: unknown, row: ApiRow) => {
        const num = Number(row.score || 0);
        if (num >= 8.5) return <Tag color="success">Xuất sắc</Tag>;
        if (num >= 8.0) return <Tag color="green">Giỏi</Tag>;
        if (num >= 6.5) return <Tag color="blue">Khá</Tag>;
        if (num >= 5.0) return <Tag color="warning">Trung bình</Tag>;
        return <Tag color="error">Cần cải thiện</Tag>;
      },
    },
    {
      title: "Ngày cập nhật",
      dataIndex: "entered_at",
      key: "entered_at",
      render: (val: unknown) => {
        if (!val) return "---";
        const d = new Date(String(val));
        return isNaN(d.getTime()) ? String(val) : d.toLocaleDateString("vi-VN");
      },
    },
  ];

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {/* Tong ket diem */}
      <Card style={{ background: "linear-gradient(135deg, #f6ffed 0%, #ffffff 100%)", border: "1px solid #b7eb8f" }}>
        <Row gutter={[24, 16]} align="middle">
          <Col xs={24} sm={8}>
            <Statistic
              title="Điểm trung bình tích lũy"
              value={avg}
              suffix="/ 10"
              prefix={<TrophyOutlined style={{ color: "#52c41a" }} />}
            />
          </Col>
          <Col xs={24} sm={8}>
            <Statistic
              title="Tổng số bài kiểm tra"
              value={grades.length}
              suffix="bài"
              prefix={<StarOutlined style={{ color: "#faad14" }} />}
            />
          </Col>
          <Col xs={24} sm={8}>
            <Statistic
              title="Tình trạng học tập"
              value={Number(avg) >= 5.0 ? "Đạt chuẩn tiến độ" : "Cần hỗ trợ"}
              valueStyle={{ color: Number(avg) >= 5.0 ? "#52c41a" : "#cf1322", fontSize: 18 }}
              prefix={<CheckCircleOutlined />}
            />
          </Col>
        </Row>
      </Card>

      {/* Bang chi tiet */}
      <Card
        title={
          <Space>
            <TrophyOutlined style={{ color: "#175245" }} />
            <span>Bảng điểm chi tiết ({grades.length} cột điểm)</span>
          </Space>
        }
      >
        <Table
          rowKey={(row) => String(row.grade_id || Math.random())}
          dataSource={grades}
          columns={columns}
          loading={loading}
          pagination={false}
          scroll={{ x: 700 }}
        />
      </Card>
    </div>
  );
}
