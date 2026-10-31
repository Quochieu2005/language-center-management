"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tabs, Typography, message } from "antd";
import { academicsApi, type ApiRow } from "@/lib/api/academics";
import { RequireSession } from "@/lib/auth/session";
import { ApiDataTable, asRows } from "@/components/shared/ApiPage";

const gradeTypes = ["giua_ky", "cuoi_ky", "nghe", "noi", "doc", "viet"];
const attendanceOptions = ["co_mat", "tre", "vang_co_phep", "vang_khong_phep"].map((value) => ({ value, label: value.replaceAll("_", " ") }));

export default function TeacherRoute() { return <RequireSession roles={["giao_vien"]}><TeacherPortal /></RequireSession>; }

function TeacherPortal() {
  const [classes, setClasses] = useState<ApiRow[]>([]);
  const [sessions, setSessions] = useState<ApiRow[]>([]);
  const [roster, setRoster] = useState<ApiRow[]>([]);
  const [attendance, setAttendance] = useState<Record<string, { status?: string; note?: string }>>({});
  const [gradeRecord, setGradeRecord] = useState<ApiRow | null>(null);
  const [gradeData, setGradeData] = useState<ApiRow | null>(null);
  const [gradeHistory, setGradeHistory] = useState<ApiRow | null>(null);
  const [activeClass, setActiveClass] = useState<ApiRow | null>(null);
  const [activeSession, setActiveSession] = useState<ApiRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form] = Form.useForm();
  const load = useCallback(async () => {
    try { const result = await academicsApi.teacherClasses(); setClasses(result.results); setError(""); }
    catch (reason) { setError(msg(reason)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);
  const chooseClass = async (row: ApiRow) => {
    setActiveClass(row); setActiveSession(null); setRoster([]);
    try { setSessions((await academicsApi.teacherSessions(String(row.class_id))).results); }
    catch (reason) { setError(msg(reason)); }
  };
  const chooseSession = async (row: ApiRow) => {
    setActiveSession(row); setError("");
    try {
      const result = await academicsApi.attendance(String(row.session_id));
      const rows = asRows(result.results); setRoster(rows);
      setAttendance(Object.fromEntries(rows.map((item) => [String(item.enrollment_id), { status: typeof item.attendance_status === "string" ? item.attendance_status : undefined, note: typeof item.note === "string" ? item.note : "" }])));
    } catch (reason) { setError(msg(reason)); }
  };
  const saveAttendance = async () => {
    if (!activeSession) return;
    const incomplete = roster.some((row) => !attendance[String(row.enrollment_id)]?.status);
    if (incomplete) { message.warning("Chọn trạng thái điểm danh cho từng học viên trước khi lưu."); return; }
    try {
      const items = roster.map((row) => ({ enrollment_id: String(row.enrollment_id), status: attendance[String(row.enrollment_id)].status as "co_mat" | "tre" | "vang_co_phep" | "vang_khong_phep", note: attendance[String(row.enrollment_id)].note || "" }));
      const result = await academicsApi.saveAttendance(String(activeSession.session_id), items);
      message.success(`Đã lưu điểm danh. Phản hồi cảnh báo email: ${JSON.stringify(result.email_alerts || {})}`);
      await chooseSession(activeSession);
    } catch (reason) { message.error(msg(reason)); }
  };
  const openGrade = async (row: ApiRow) => {
    setGradeRecord(row); setGradeData(null); setGradeHistory(null);
    try {
      const [grades, history] = await Promise.all([academicsApi.grades(String(row.enrollment_id)), academicsApi.gradeHistory(String(row.enrollment_id))]);
      setGradeData(grades); setGradeHistory(history);
    } catch (reason) { message.error(msg(reason)); }
  };
  const saveGrade = async (values: { grade_type: string; score: number }) => {
    if (!gradeRecord) return;
    try { await academicsApi.saveGrade(String(gradeRecord.enrollment_id), values.grade_type, values.score); message.success("Đã lưu điểm và nhật ký thay đổi."); await openGrade(gradeRecord); form.resetFields(); }
    catch (reason) { message.error(msg(reason)); }
  };
  const sessionColumns = [
    { title: "Buổi", dataIndex: "sequence" }, { title: "Ngày", dataIndex: "session_date" }, { title: "Giờ", render: (_: unknown, row: ApiRow) => `${String(row.start_time || "")}–${String(row.end_time || "")}` },
    { title: "Phòng", dataIndex: "room_name" }, { title: "Trạng thái", dataIndex: "status" }, { title: "Thao tác", render: (_: unknown, row: ApiRow) => <Button onClick={() => void chooseSession(row)}>Điểm danh</Button> },
  ];
  return <main style={{ maxWidth: 1200, margin: "24px auto", padding: 16 }}><Space direction="vertical" size="middle" style={{ width: "100%" }}><Typography.Title level={2}>Không gian giáo viên</Typography.Title>
    {error && <Alert type="error" showIcon title={error} />}
    <Card title="Lớp được phân công"><ApiDataTable rows={classes} loading={loading} emptyText="Chưa được phân công lớp" onRow={(row) => ({ onClick: () => void chooseClass(row) })} />{classes.length > 0 && <Select placeholder="Chọn lớp để xem buổi học" style={{ width: "100%", marginTop: 12 }} value={activeClass ? String(activeClass.class_id) : undefined} onChange={(value) => { const found = classes.find((row) => String(row.class_id) === value); if (found) void chooseClass(found); }} options={classes.map((row) => ({ value: String(row.class_id), label: `${String(row.name || row.class_name || row.class_id)} · ${String(row.site_code || "")}` }))} />}</Card>
    {activeClass && <Card title={`Buổi học · ${String(activeClass.name || activeClass.class_name || activeClass.class_id)}`}><Table rowKey={(row) => String(row.session_id)} dataSource={sessions} columns={sessionColumns} pagination={{ pageSize: 8 }} scroll={{ x: 750 }} /></Card>}
    {activeSession && <Card title={`Điểm danh · ${String(activeSession.session_date || "")}`} extra={<Button type="primary" onClick={() => void saveAttendance()}>Lưu điểm danh</Button>}><Table rowKey={(row) => String(row.enrollment_id)} dataSource={roster} pagination={false} scroll={{ x: 850 }} columns={[{ title: "Học viên", dataIndex: "student_name" }, { title: "Mã đăng ký", dataIndex: "enrollment_id" }, { title: "Trạng thái", render: (_: unknown, row: ApiRow) => <Select value={attendance[String(row.enrollment_id)]?.status} placeholder="Chọn trạng thái" options={attendanceOptions} onChange={(value) => setAttendance((prev) => ({ ...prev, [String(row.enrollment_id)]: { ...prev[String(row.enrollment_id)], status: value } }))} style={{ width: 180 }} /> }, { title: "Ghi chú", render: (_: unknown, row: ApiRow) => <Input maxLength={500} value={attendance[String(row.enrollment_id)]?.note} onChange={(event) => setAttendance((prev) => ({ ...prev, [String(row.enrollment_id)]: { ...prev[String(row.enrollment_id)], note: event.target.value } }))} /> }, { title: "Điểm", render: (_: unknown, row: ApiRow) => <Button onClick={() => void openGrade(row)}>Xem / nhập điểm</Button> }]} /></Card>}
    <Modal title={`Điểm · ${String(gradeRecord?.student_name || "Học viên")}`} open={Boolean(gradeRecord)} onCancel={() => setGradeRecord(null)} footer={null} width={760}><Form form={form} layout="inline" onFinish={saveGrade}><Form.Item name="grade_type" rules={[{ required: true }]}><Select placeholder="Loại điểm" style={{ width: 160 }} options={gradeTypes.map((value) => ({ value, label: value.replaceAll("_", " ") }))} /></Form.Item><Form.Item name="score" rules={[{ required: true }]}><InputNumber min={0} max={10} step={0.25} placeholder="0–10" /></Form.Item><Button type="primary" htmlType="submit">Lưu điểm</Button></Form><Tabs style={{ marginTop: 20 }} items={[{ key: "grades", label: "Điểm hiện tại", children: <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(gradeData, null, 2)}</pre> }, { key: "history", label: "Lịch sử", children: <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(gradeHistory, null, 2)}</pre> }]} /></Modal>
  </Space></main>;
}

function msg(reason: unknown) { return reason instanceof Error ? reason.message : "Yêu cầu API thất bại."; }
