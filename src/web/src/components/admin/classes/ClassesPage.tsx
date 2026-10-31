"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Checkbox, Descriptions, Form, Input, InputNumber, Modal, Select, Space, Table, Tabs, Tag, message } from "antd";
import { academicsApi, type ClassRow, type EnrollmentRow, type RoomRow, type SessionRow } from "@/lib/api/academics";
import { adminApi, type Student, type Teacher } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

const weekdays = [2, 3, 4, 5, 6].map((value) => ({ value, label: `Thứ ${value}` }));

export default function ClassesPage() {
  const { user } = useSession();
  const canManage = ["admin_big", "admin_small", "le_tan", "xep_lop"].includes(user?.role || "");
  const canEnroll = canManage || user?.role === "tu_van";
  const { selectedSite } = useSiteScope();
  const site = user?.role === "admin_big" ? selectedSite : user?.site_code || null;
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [rooms, setRooms] = useState<RoomRow[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [detail, setDetail] = useState<ClassRow | null>(null);
  const [roster, setRoster] = useState<EnrollmentRow[]>([]);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [modal, setModal] = useState<"class" | "room" | "enroll" | "move" | "teacher" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [classForm] = Form.useForm();
  const [simpleForm] = Form.useForm();

  const load = useCallback(async () => {
    if (!site) return;
    const [classResult, roomResult, teacherResult, studentResult] = await Promise.allSettled([
      academicsApi.classes(site),
      canManage ? academicsApi.rooms(site) : Promise.resolve({ results: [] as RoomRow[] }),
      canManage ? adminApi.teachers(site) : Promise.resolve({ results: [] as Teacher[] }),
      adminApi.students({ site_code: site, limit: 100 }),
    ]);
    if (classResult.status === "fulfilled") setClasses(classResult.value.results); else setError(reason(classResult.reason));
    if (roomResult.status === "fulfilled") setRooms(roomResult.value.results); else setError((old) => [old, reason(roomResult.reason)].filter(Boolean).join(" · "));
    if (teacherResult.status === "fulfilled") setTeachers(teacherResult.value.results); else setError((old) => [old, reason(teacherResult.reason)].filter(Boolean).join(" · "));
    if (studentResult.status === "fulfilled") setStudents(studentResult.value.results); else setError((old) => [old, reason(studentResult.reason)].filter(Boolean).join(" · "));
    setError([classResult, roomResult, teacherResult, studentResult].filter((item) => item.status === "rejected").map((item) => item.status === "rejected" ? reason(item.reason) : "").filter(Boolean).join(" · "));
    setLoading(false);
  }, [canManage, site]);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);

  const showClass = async (row: ClassRow) => {
    if (!site) return;
    setDetail(row); setModal(null);
    const [detailResult, rosterResult, sessionResult] = await Promise.allSettled([
      academicsApi.classDetail(row.class_id, site),
      canManage ? academicsApi.roster(row.class_id, site) : Promise.resolve({ results: [] as EnrollmentRow[] }),
      academicsApi.classSessions(row.class_id, site),
    ]);
    if (detailResult.status === "fulfilled") setDetail(detailResult.value);
    if (rosterResult.status === "fulfilled") setRoster(rosterResult.value.results);
    if (sessionResult.status === "fulfilled") setSessions(sessionResult.value.results);
  };
  const createClass = async (values: Record<string, string | number | number[]>) => {
    if (!site) return;
    try {
      await academicsApi.createClass({ site_code: site, course_id: String(values.course_id), teacher_id: String(values.teacher_id), room_id: String(values.room_id), name: String(values.name), capacity: Number(values.capacity), start_date: String(values.start_date), end_date: String(values.end_date), weekdays: values.weekdays as number[], start_time: String(values.start_time), end_time: String(values.end_time) });
      message.success("Đã tạo lớp và lịch buổi học tại site."); setModal(null); classForm.resetFields(); void load();
    } catch (error) { message.error(reason(error)); }
  };
  const createRoom = async (values: { name: string; capacity: number }) => {
    if (!site) return;
    try { await academicsApi.createRoom({ site_code: site, ...values }); message.success("Đã thêm phòng học."); setModal(null); simpleForm.resetFields(); void load(); }
    catch (error) { message.error(reason(error)); }
  };
  const enroll = async (values: { student_id: string; class_id: string }) => {
    if (!site) return;
    try { await academicsApi.enroll({ site_code: site, ...values }); message.success("Đăng ký và khoản học phí được xử lý trong transaction tại cơ sở."); setModal(null); simpleForm.resetFields(); void load(); }
    catch (error) { message.error(reason(error)); }
  };
  const moveEnrollment = async (values: { enrollment_id: string; target_class_id: string }) => {
    if (!site) return;
    try { await academicsApi.moveEnrollment(values.enrollment_id, site, values.target_class_id); message.success("Đã xếp lại lớp tại site."); setModal(null); simpleForm.resetFields(); void load(); }
    catch (error) { message.error(reason(error)); }
  };
  const assignTeacher = async (values: { teacher_id: string }) => {
    if (!site || !detail) return;
    try { await academicsApi.assignTeacher(detail.class_id, site, values.teacher_id); message.success("Đã cập nhật giáo viên và lịch buổi theo API."); setModal(null); void load(); void showClass(detail); }
    catch (error) { message.error(reason(error)); }
  };
  const columns = [
    { title: "Lớp", dataIndex: "name", render: (value: string, row: ClassRow) => <Button type="link" onClick={() => void showClass(row)}>{value}</Button> },
    { title: "Khóa học", dataIndex: "course_name" }, { title: "Giáo viên", dataIndex: "teacher_name" }, { title: "Phòng", dataIndex: "room_name" },
    { title: "Lịch", dataIndex: "schedule" }, { title: "Ngày", render: (_: unknown, row: ClassRow) => `${row.start_date} – ${row.end_date || "—"}` },
    { title: "Sĩ số", render: (_: unknown, row: ClassRow) => <span>{row.registered_count}/{row.capacity} · còn {row.remaining_seats}</span> },
    { title: "Trạng thái", dataIndex: "status", render: (value: string) => <Tag>{value}</Tag> },
  ];
  return <Space direction="vertical" size="middle" style={{ width: "100%" }}>
    {!site && <Alert type="warning" showIcon title="Chưa có site được chọn hoặc phiên chưa trả phạm vi cơ sở." />}
    {error && <Alert type="error" showIcon title={error} />}
    <Card title={`Lớp học${site ? ` · ${site}` : ""}`} extra={<Space wrap>{canManage && <><Button onClick={() => setModal("room")}>Thêm phòng</Button><Button onClick={() => setModal("move")}>Chuyển lớp</Button></>}{canEnroll && <Button onClick={() => setModal("enroll")}>Đăng ký học</Button>}{canManage && <Button type="primary" onClick={() => setModal("class")} disabled={!site}>Mở lớp</Button>}</Space>}>
      <Table rowKey="class_id" loading={loading} columns={columns} dataSource={classes} scroll={{ x: 1000 }} />
    </Card>
    <Modal title="Tạo lớp và lịch" open={modal === "class"} onCancel={() => setModal(null)} footer={null} width={700} destroyOnClose><Form form={classForm} layout="vertical" onFinish={createClass}>
      <Form.Item name="name" label="Tên lớp" rules={[{ required: true }]}><Input maxLength={120} /></Form.Item>
      <Form.Item name="course_id" label="Mã khóa học có sẵn tại site" rules={[{ required: true }]}><Input maxLength={30} /></Form.Item>
      <Form.Item name="teacher_id" label="Giáo viên" rules={[{ required: true }]}><Select options={teachers.filter((x) => x.status === "dang_day").map((x) => ({ value: x.teacher_id, label: `${x.full_name} · ${x.teacher_id}` }))} /></Form.Item>
      <Form.Item name="room_id" label="Phòng" rules={[{ required: true }]}><Select options={rooms.filter((x) => x.status === "hoat_dong").map((x) => ({ value: x.room_id, label: `${x.name} · tối đa ${x.capacity}` }))} /></Form.Item>
      <Form.Item name="capacity" label="Sĩ số tối đa" rules={[{ required: true }]}><InputNumber min={1} max={300} style={{ width: "100%" }} /></Form.Item>
      <Space wrap><Form.Item name="start_date" label="Ngày bắt đầu" rules={[{ required: true }]}><Input type="date" /></Form.Item><Form.Item name="end_date" label="Ngày kết thúc" rules={[{ required: true }]}><Input type="date" /></Form.Item><Form.Item name="start_time" label="Giờ bắt đầu" rules={[{ required: true }]}><Input type="time" /></Form.Item><Form.Item name="end_time" label="Giờ kết thúc" rules={[{ required: true }]}><Input type="time" /></Form.Item></Space>
      <Form.Item name="weekdays" label="Ngày học trong tuần" rules={[{ required: true }]}><Checkbox.Group options={weekdays} /></Form.Item>
      <Button type="primary" htmlType="submit" block>Tạo lớp</Button>
    </Form></Modal>
    <Modal title="Tạo phòng học" open={modal === "room"} onCancel={() => setModal(null)} footer={null}><Form form={simpleForm} layout="vertical" onFinish={createRoom}><Form.Item name="name" label="Tên phòng" rules={[{ required: true }]}><Input maxLength={100} /></Form.Item><Form.Item name="capacity" label="Sức chứa" rules={[{ required: true }]}><InputNumber min={1} max={300} style={{ width: "100%" }} /></Form.Item><Button type="primary" htmlType="submit" block>Tạo phòng</Button></Form></Modal>
    <Modal title="Đăng ký học viên vào lớp" open={modal === "enroll"} onCancel={() => setModal(null)} footer={null}><Form form={simpleForm} layout="vertical" onFinish={enroll}><Form.Item name="student_id" label="Học viên" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" options={students.map((x) => ({ value: x.student_id, label: `${x.full_name} · ${x.student_id}` }))} /></Form.Item><Form.Item name="class_id" label="Lớp" rules={[{ required: true }]}><Select options={classes.map((x) => ({ value: x.class_id, label: `${x.name} · còn ${x.remaining_seats}` }))} /></Form.Item><Button type="primary" htmlType="submit" block>Đăng ký</Button></Form></Modal>
    <Modal title="Chuyển đăng ký sang lớp khác" open={modal === "move"} onCancel={() => setModal(null)} footer={null}><Form form={simpleForm} layout="vertical" onFinish={moveEnrollment}><Form.Item name="enrollment_id" label="Mã đăng ký" rules={[{ required: true }]}><Input maxLength={24} /></Form.Item><Form.Item name="target_class_id" label="Lớp đích" rules={[{ required: true }]}><Select options={classes.map((x) => ({ value: x.class_id, label: `${x.name} · ${x.schedule}` }))} /></Form.Item><Button type="primary" htmlType="submit" block>Xếp lớp lại</Button></Form></Modal>
    <Modal title="Chi tiết lớp" open={Boolean(detail)} onCancel={() => setDetail(null)} footer={<Space>{canManage && <Button onClick={() => setModal("teacher")}>Đổi giáo viên</Button>}<Button onClick={() => setDetail(null)}>Đóng</Button></Space>} width={900}><Descriptions size="small" column={2} items={detail ? [{ key: "id", label: "Mã lớp", children: detail.class_id }, { key: "site", label: "Cơ sở", children: detail.site_code }, { key: "count", label: "Sĩ số", children: `${detail.registered_count}/${detail.capacity}` }, { key: "schedule", label: "Lịch", children: detail.schedule }] : []} /><Tabs items={[...(canManage ? [{ key: "students", label: `Học viên (${roster.length})`, children: <Table rowKey="enrollment_id" size="small" dataSource={roster} columns={[{ title: "Tên", dataIndex: "full_name" }, { title: "Mã học viên", dataIndex: "student_id" }, { title: "Đăng ký", dataIndex: "enrollment_status" }]} /> }] : []), { key: "sessions", label: `Buổi học (${sessions.length})`, children: <Table rowKey="session_id" size="small" dataSource={sessions} columns={[{ title: "Buổi", dataIndex: "session_number" }, { title: "Ngày", dataIndex: "date" }, { title: "Giờ", render: (_: unknown, x: SessionRow) => `${x.start_time}–${x.end_time}` }, { title: "Phòng", dataIndex: "room_name" }, { title: "Trạng thái", dataIndex: "status" }]} /> }]} /></Modal>
    <Modal title="Phân công giáo viên" open={modal === "teacher"} onCancel={() => setModal(null)} footer={null}><Form layout="vertical" onFinish={assignTeacher}><Form.Item name="teacher_id" label="Giáo viên đang hoạt động" rules={[{ required: true }]}><Select options={teachers.filter((x) => x.status === "dang_day").map((x) => ({ value: x.teacher_id, label: x.full_name }))} /></Form.Item><Button type="primary" htmlType="submit" block>Lưu phân công</Button></Form></Modal>
  </Space>;
}

function reason(error: unknown) { return error instanceof Error ? error.message : "Yêu cầu API thất bại."; }
