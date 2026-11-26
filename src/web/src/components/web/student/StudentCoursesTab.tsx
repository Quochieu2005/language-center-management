"use client";

import { Card, Tag, Typography, Button, Empty, Row, Col } from "antd";
import {
  CalendarOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  RightOutlined
} from "@ant-design/icons";
import Link from "next/link";
import type { ApiRow } from "@/lib/api/academics";
import styles from "./StudentPortal.module.scss";
import portal from "@/components/web/shared/Portal.module.scss";

type Props = {
  enrollments: ApiRow[];
  onSelectTab: (key: string) => void;
};

export function StudentCoursesTab({ enrollments, onSelectTab }: Props) {
  if (enrollments.length === 0) {
    return (
      <Card>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="Bạn chưa đăng ký lớp học nào tại trung tâm."
        >
          <Link href="/courses">
            <Button type="primary">Khám phá các khóa học đang mở</Button>
          </Link>
        </Empty>
      </Card>
    );
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Typography.Title level={4} style={{ margin: "0 0 8px" }}>
        Danh sách lớp học đang theo học ({enrollments.length})
      </Typography.Title>

      <Row gutter={[16, 16]}>
        {enrollments.map((item, idx) => (
          <Col xs={24} md={12} key={String(item.enrollment_id || idx)}>
            <Card
              className={styles.courseCard}
              title={
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <Typography.Text strong className={portal.accent} style={{ fontSize: 16 }}>
                    {String(item.class_name || "Lớp học")}
                  </Typography.Text>
                  <Tag color="green">Đang học</Tag>
                </div>
              }
              extra={
                <Button type="link" size="small" onClick={() => onSelectTab("schedule")}>
                  Xem lịch học <RightOutlined />
                </Button>
              }
            >
              <div style={{ display: "grid", gap: 10 }}>
                <div>
                  <Typography.Text type="secondary">Khóa học:</Typography.Text>{" "}
                  <strong>{String(item.course_name || item.subject_name || "---")}</strong>
                </div>
                <div>
                  <Typography.Text type="secondary">Mã đăng ký:</Typography.Text>{" "}
                  <code>{String(item.enrollment_id || "---")}</code>
                </div>
                <div>
                  <CalendarOutlined className={portal.accent} style={{ marginRight: 6 }}/>
                  <span>Thời gian học: <strong>{String(item.schedule || "---")}</strong></span>
                </div>
                <div>
                  <ClockCircleOutlined className={portal.accent} style={{ marginRight: 6 }}/>
                  <span>Khung giờ: <strong>{String(item.start_time || "")} - {String(item.end_time || "")}</strong></span>
                </div>
                {Boolean(item.start_date) && (
                  <div>
                    <EnvironmentOutlined className={portal.accent} style={{ marginRight: 6 }}/>
                    <span>Lộ trình: {String(item.start_date)} đến {String(item.end_date || "Kết khóa")}</span>
                  </div>
                )}
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
