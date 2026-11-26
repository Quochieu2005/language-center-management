"use client";

import { useEffect, useState } from "react";
import {
  Card,
  Table,
  Select,
  Button,
  Modal,
  Form,
  InputNumber,
  Tag,
  Row,
  Col,
  Typography,
  message,
  Empty,
  Spin,
} from "antd";
import {
  EditOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { academicsApi, type ApiRow } from "@/lib/api/academics";
import styles from "./TeacherPortal.module.scss";
import portal from "@/components/web/shared/Portal.module.scss";

type TeacherGradesTabProps = {
  classes: ApiRow[];
  activeClass: ApiRow | null;
  roster: ApiRow[];
  selectedStudent: ApiRow | null;
  onSelectClass: (cls: ApiRow) => void;
  onCloseStudentModal: () => void;
  onOpenStudentModal: (student: ApiRow) => void;
};

const GRADE_TYPES = [
  { value: "giua_ky", label: "Giữa kỳ" },
  { value: "cuoi_ky", label: "Cuối kỳ" },
  { value: "nghe", label: "Kỹ năng Nghe (Listening)" },
  { value: "noi", label: "Kỹ năng Nói (Speaking)" },
  { value: "doc", label: "Kỹ năng Đọc (Reading)" },
  { value: "viet", label: "Kỹ năng Viết (Writing)" },
];

export function TeacherGradesTab({
  classes,
  activeClass,
  roster,
  selectedStudent,
  onSelectClass,
  onCloseStudentModal,
  onOpenStudentModal,
}: TeacherGradesTabProps) {
  const [form] = Form.useForm();
  const [savingGrade, setSavingGrade] = useState(false);
  const [loadingGrades, setLoadingGrades] = useState(false);
  const [gradeData, setGradeData] = useState<ApiRow | null>(null);
  const [gradeHistory, setGradeHistory] = useState<ApiRow[]>([]);
  const [loadedEnrollmentId, setLoadedEnrollmentId] = useState<string | null>(null);

  // Fetch grades & audit history when a student is selected
  useEffect(() => {
    if (!selectedStudent) return;

    const eid = String(selectedStudent.enrollment_id);
    let cancelled = false;

    async function loadStudentGrades() {
      setLoadingGrades(true);
      try {
        const [gradesRes, historyRes] = await Promise.all([
          academicsApi.grades(eid),
          academicsApi.gradeHistory(eid),
        ]);
        if (!cancelled) {
          setLoadedEnrollmentId(eid);
          setGradeData(gradesRes);
          const hist = Array.isArray(historyRes.results) ? historyRes.results : [];
          setGradeHistory(hist as ApiRow[]);
        }
      } catch (err) {
        if (!cancelled) {
          message.error(err instanceof Error ? err.message : "Không thể tải điểm của học viên.");
        }
      } finally {
        if (!cancelled) {
          setLoadingGrades(false);
        }
      }
    }

    void loadStudentGrades();
    return () => {
      cancelled = true;
    };
  }, [selectedStudent]);

  const handleSaveGrade = async (values: { grade_type: string; score: number }) => {
    if (!selectedStudent) return;
    setSavingGrade(true);
    const eid = String(selectedStudent.enrollment_id);
    try {
      await academicsApi.saveGrade(eid, values.grade_type, values.score);
      message.success("Đã ghi nhận điểm và tạo nhật ký kiểm toán hệ thống.");
      form.resetFields();

      // Refresh grades & history
      const [gradesRes, historyRes] = await Promise.all([
        academicsApi.grades(eid),
        academicsApi.gradeHistory(eid),
      ]);
      setLoadedEnrollmentId(eid);
      setGradeData(gradesRes);
      const hist = Array.isArray(historyRes.results) ? historyRes.results : [];
      setGradeHistory(hist as ApiRow[]);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Lỗi khi lưu điểm.");
    } finally {
      setSavingGrade(false);
    }
  };

  const getScoreBadge = (scoreVal: unknown) => {
    if (scoreVal === null || scoreVal === undefined || scoreVal === "") {
      return <span className={`${styles.scoreBadge} ${styles.none}`}>—</span>;
    }
    const score = Number(scoreVal);
    let badgeClass = styles.low;
    if (score >= 8.0) badgeClass = styles.high;
    else if (score >= 5.0) badgeClass = styles.medium;

    return <span className={`${styles.scoreBadge} ${badgeClass}`}>{score.toFixed(1)}</span>;
  };

  const hasCurrentStudentGrades = Boolean(selectedStudent)
    && loadedEnrollmentId === String(selectedStudent?.enrollment_id);
  const currentGradeList = hasCurrentStudentGrades && Array.isArray(gradeData?.results)
    ? (gradeData.results as ApiRow[])
    : [];
  const currentGradeHistory = hasCurrentStudentGrades ? gradeHistory : [];

  const gradeColumns = [
    {
      title: "Mã học viên",
      dataIndex: "student_id",
      key: "student_id",
      width: 140,
      render: (val: unknown) => <Tag color="geekblue">{String(val || "—")}</Tag>,
    },
    {
      title: "Họ và tên",
      dataIndex: "student_name",
      key: "student_name",
      render: (val: unknown) => (
        <div>
          <strong>{String(val || "—")}</strong>
        </div>
      ),
    },
    {
      title: "Mã đăng ký",
      dataIndex: "enrollment_id",
      key: "enrollment_id",
      width: 150,
      render: (val: unknown) => <span style={{ color: "#64748b" }}>{String(val || "—")}</span>,
    },
    {
      title: "Trạng thái",
      dataIndex: "enrollment_status",
      key: "enrollment_status",
      width: 130,
      render: (val: unknown) => {
        const s = String(val);
        return <Tag color={s === "dang_hoc" ? "green" : "default"}>{s === "dang_hoc" ? "Đang học" : s}</Tag>;
      },
    },
    {
      title: "Thao tác",
      key: "actions",
      width: 180,
      render: (_: unknown, row: ApiRow) => (
        <Button
          type="primary"
          size="small"
          icon={<EditOutlined />}
          onClick={() => onOpenStudentModal(row)}
        >
          Nhập / Xem điểm
        </Button>
      ),
    },
  ];

  return (
    <div>
      {/* Class Selector */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={12}>
            <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
              Chọn Lớp học để chấm điểm:
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
        </Row>
      </Card>

      {/* Roster Grading Table */}
      <Card
        title={
          <span>
            Bảng điểm học viên: <strong>{activeClass ? String(activeClass.name || activeClass.class_id) : "Chưa chọn lớp"}</strong>
          </span>
        }
      >
        {!activeClass ? (
          <Empty description="Vui lòng chọn lớp học để xem danh sách học viên và quản lý điểm số." />
        ) : roster.length === 0 ? (
          <Empty description="Lớp học này hiện chưa có học viên nào đăng ký." />
        ) : (
          <Table
            rowKey={(r) => String(r.enrollment_id)}
            dataSource={roster}
            columns={gradeColumns}
            pagination={false}
            scroll={{ x: 750 }}
          />
        )}
      </Card>

      {/* Modal: Grade Input & Audit History */}
      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <UserOutlined className={portal.accent} />
            <span>
              Bảng điểm học viên: <strong>{String(selectedStudent?.student_name || "Học viên")}</strong>
            </span>
          </div>
        }
        open={Boolean(selectedStudent)}
        onCancel={onCloseStudentModal}
        footer={null}
        width={780}
      >
        {loadingGrades ? (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <Spin size="large" />
          </div>
        ) : (
          <div>
            {/* Grade summary cards */}
            <Typography.Title level={5} style={{ margin: "12px 0 8px" }}>
              Điểm số hiện tại
            </Typography.Title>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10, marginBottom: 20 }}>
              {GRADE_TYPES.map((gt) => {
                const rec = currentGradeList.find((g) => String(g.grade_type) === gt.value);
                return (
                  <div
                    key={gt.value}
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: 10,
                      padding: "10px 8px",
                      textAlign: "center",
                    }}
                  >
                    <div style={{ fontSize: 12, color: "#64748b", marginBottom: 6, fontWeight: 500 }}>
                      {gt.label.split(" ")[0]}
                    </div>
                    <div>{getScoreBadge(rec?.score)}</div>
                  </div>
                );
              })}
            </div>

            {/* Input Form */}
            <Card
              title={
                <span>
                  <EditOutlined className={portal.accent} style={{ marginRight: 6 }}/>
                  Nhập / Cập nhật điểm
                </span>
              }
              size="small"
              style={{ marginBottom: 20 }}
            >
              <Form form={form} layout="inline" onFinish={handleSaveGrade}>
                <Form.Item name="grade_type" rules={[{ required: true, message: "Chọn loại điểm" }]}>
                  <Select placeholder="Chọn đầu điểm" style={{ width: 220 }} options={GRADE_TYPES} />
                </Form.Item>
                <Form.Item name="score" rules={[{ required: true, message: "Nhập điểm từ 0 đến 10" }]}>
                  <InputNumber min={0} max={10} step={0.25} placeholder="Điểm (0–10)" style={{ width: 130 }} />
                </Form.Item>
                <Form.Item>
                  <Button type="primary" htmlType="submit" loading={savingGrade} icon={<CheckCircleOutlined />}>
                    Lưu điểm
                  </Button>
                </Form.Item>
              </Form>
            </Card>

            {/* Audit History Tabs */}
            <Typography.Title level={5} style={{ margin: "16px 0 8px" }}>
              <HistoryOutlined className={portal.accent} style={{ marginRight: 8 }}/>
              Nhật ký kiểm toán thay đổi điểm ({currentGradeHistory.length})
            </Typography.Title>
            {currentGradeHistory.length === 0 ? (
              <div style={{ textAlign: "center", padding: 20, color: "#94a3b8" }}>
                Chưa có lịch sử điều chỉnh điểm cho học viên này.
              </div>
            ) : (
              <div style={{ maxHeight: 240, overflowY: "auto", paddingRight: 6 }}>
                {currentGradeHistory.map((h, i) => {
                  let beforeVal = "Chưa có";
                  let afterVal = "";
                  try {
                    const b = typeof h.before_json === "string" ? JSON.parse(h.before_json) : h.before_json;
                    const a = typeof h.after_json === "string" ? JSON.parse(h.after_json) : h.after_json;
                    if (b?.score !== undefined) beforeVal = `${b.score}`;
                    if (a?.score !== undefined) afterVal = `${a.score} (${a.grade_type || ""})`;
                  } catch {
                    // fallback
                  }

                  return (
                    <div key={String(h.log_id || i)} className={styles.auditLogCard}>
                      <div className={styles.logHeader}>
                        <span>
                          <ClockCircleOutlined style={{ marginRight: 4 }} />
                          {String(h.occurred_at || "")}
                        </span>
                        <span>Người thực hiện: {String(h.actor_id || "Hệ thống")}</span>
                      </div>
                      <div className={styles.logDetails}>
                        Thay đổi: <Tag color="default">{beforeVal}</Tag> ➔ <Tag color="green">{afterVal || "Điểm mới"}</Tag>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
