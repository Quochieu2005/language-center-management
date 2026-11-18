"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Checkbox, Descriptions, Form, Input, InputNumber, Modal, Select, Space, Table, Tabs, Tag, message } from "antd";
import { academicsApi, type ClassRow, type EnrollmentRow, type RoomRow, type SessionRow } from "@/lib/api/academics";
import { adminApi, type Student, type Teacher } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { ALL_SITES, useSiteScope } from "@/lib/auth/site-scope";

const weekdays = [2, 3, 4, 5, 6].map((value) => ({ value, label: `Thứ ${value}` }));

export default function ClassesPage() {
  const { user } = useSession();
  const canViewRoster = ["admin_big", "admin_small", "le_tan", "tu_van", "ke_toan"].includes(user?.role || "");
  const canWriteClasses = ["admin_big", "admin_small", "tu_van"].includes(user?.role || "");
  const canEnroll = canWriteClasses;
  const canAdministerClasses = canWriteClasses;
  const { selectedSite, siteCodes, loadingSites, setSelectedSite } = useSiteScope();
  const isAdminBig = user?.role === "admin_big";
  const site = user?.role === "admin_big" ? selectedSite : user?.site_code || null;
  const isSpecificSite = Boolean(site && site !== ALL_SITES);
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [operationClasses, setOperationClasses] = useState<ClassRow[]>([]);
  const [sourceClassId, setSourceClassId] = useState("");
  const [moveEnrollments, setMoveEnrollments] = useState<EnrollmentRow[]>([]);
  const [moveRosterLoading, setMoveRosterLoading] = useState(false);
  const [rooms, setRooms] = useState<RoomRow[]>([]);
  const [teachers, setTeachers] = useState<Array<Pick<Teacher, "teacher_id" | "full_name">>>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [operationSite, setOperationSite] = useState("");
  const [operationLoading, setOperationLoading] = useState(false);
  const [operationError, setOperationError] = useState("");
  const [detail, setDetail] = useState<ClassRow | null>(null);
  const [roster, setRoster] = useState<EnrollmentRow[]>([]);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [modal, setModal] = useState<"class" | "enroll" | "move" | "teacher" | null>(null);
  const [editingClass, setEditingClass] = useState<ClassRow | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [partial, setPartial] = useState<string[]>([]);
  const [classForm] = Form.useForm();
  const [simpleForm] = Form.useForm();
  const actionSite = isAdminBig ? operationSite : site || "";
  const canStartOperation = canEnroll && (isAdminBig ? !loadingSites && siteCodes.length > 0 : isSpecificSite);
  const sourceClass = operationClasses.find((item) => item.class_id === sourceClassId);
  const targetClasses = operationClasses.filter((item) => item.class_id !== sourceClassId && item.course_id === sourceClass?.course_id && ["sap_mo", "dang_hoc"].includes(item.status) && item.remaining_seats > 0);

  const load = useCallback(async () => {
    if (!site) return;
    setLoading(true);
    setError("");
    setPartial([]);
    const localSite = isSpecificSite ? site : undefined;
    try {
      const result = await academicsApi.classes(localSite, { limit: 100 });
      setClasses(result.results);
      setPartial(result.missing_sites || []);
    } catch (error) {
      setClasses([]);
      setError(reason(error));
    } finally {
      setLoading(false);
    }
  }, [isSpecificSite, site]);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);

  useEffect(() => {
    if (!modal || !actionSite) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      const requests: Promise<unknown>[] = [];
      if (modal === "class" && !editingClass) {
        requests.push(academicsApi.rooms(actionSite).then((result) => { if (!cancelled) setRooms(result.results); }));
        requests.push(adminApi.teacherAssignmentOptions(isAdminBig ? actionSite : undefined, { limit: 100 }).then((result) => { if (!cancelled) setTeachers(result.results); }));
      }
      if (modal === "teacher") {
        requests.push(adminApi.teacherAssignmentOptions(isAdminBig ? actionSite : undefined, { limit: 100 }).then((result) => { if (!cancelled) setTeachers(result.results); }));
      }
      if (modal === "enroll") {
        requests.push(adminApi.students({ ...(isAdminBig ? { site_code: actionSite } : {}), limit: 100 }).then((result) => { if (!cancelled) setStudents(result.results); }));
      }
      if (modal === "enroll" || modal === "move") {
        requests.push(academicsApi.classes(actionSite, { limit: 100 }).then((result) => { if (!cancelled) setOperationClasses(result.results); }));
      }
      if (!requests.length) return;
      setOperationLoading(true);
      void Promise.allSettled(requests).then((results) => {
        if (cancelled) return;
        setOperationError(results.filter((result) => result.status === "rejected").map((result) => result.status === "rejected" ? reason(result.reason) : "").join(" · "));
        setOperationLoading(false);
      });
    });
    return () => { cancelled = true; };
  }, [actionSite, editingClass, isAdminBig, modal]);

  useEffect(() => {
    if (modal !== "move" || !actionSite || !sourceClassId) {
      setMoveEnrollments([]);
      setMoveRosterLoading(false);
      return;
    }
    let cancelled = false;
    const loadRoster = async () => {
      setMoveRosterLoading(true);
      setOperationError("");
      try {
        const first = await academicsApi.roster(sourceClassId, actionSite);
        const results = [...first.results];
        for (let offset = first.limit; offset < (first.count ?? results.length); offset += first.limit) {
          const page = await academicsApi.roster(sourceClassId, actionSite, offset);
          results.push(...page.results);
          if (!page.results.length) break;
        }
        if (!cancelled) setMoveEnrollments(results);
      } catch (error) {
        if (!cancelled) setOperationError(reason(error));
      } finally {
        if (!cancelled) setMoveRosterLoading(false);
      }
    };
    void loadRoster();
    return () => { cancelled = true; };
  }, [actionSite, modal, sourceClassId]);

  const openOperation = (next: "class" | "enroll" | "move" | "teacher", siteCode?: string) => {
    setOperationClasses([]); setRooms([]); setTeachers([]); setStudents([]); setOperationLoading(false);
    setSourceClassId(""); setMoveEnrollments([]); setMoveRosterLoading(false);
    setOperationSite(siteCode || (isSpecificSite ? site || "" : operationSite));
    setOperationError("");
    setEditingClass(null);
    classForm.resetFields();
    simpleForm.resetFields();
    setModal(next);
  };
  const refreshAfterWrite = (siteCode: string) => {
    if (isAdminBig && isSpecificSite && site !== siteCode) setSelectedSite(siteCode);
    else void load();
  };
  const operationSiteField = isAdminBig && <Form.Item label="Cơ sở thao tác" required>
    {modal === "teacher" && detail
      ? <Input value={detail.site_code} disabled />
      : modal === "class" && editingClass
        ? <Input value={editingClass.site_code} disabled />
      : <Select value={operationSite || undefined} loading={loadingSites} onChange={(value) => { setOperationSite(value); setOperationError(""); setOperationClasses([]); setRooms([]); setTeachers([]); setStudents([]); setSourceClassId(""); setMoveEnrollments([]); setMoveRosterLoading(false); setOperationLoading(false); classForm.resetFields(); simpleForm.resetFields(); }} options={siteCodes.map((value) => ({ value, label: value }))} placeholder="Chọn cơ sở để thực hiện" />}
  </Form.Item>;
  const operationAlert = operationError && <Alert type="error" showIcon title={operationError} />;
  const operationSubmitDisabled = !actionSite || operationLoading || moveRosterLoading || Boolean(operationError);

  const showClass = async (row: ClassRow) => {
    setDetail(row); setModal(null);
    const [detailResult, rosterResult, sessionResult] = await Promise.allSettled([
      academicsApi.classDetail(row.class_id, row.site_code),
      canViewRoster ? academicsApi.roster(row.class_id, row.site_code) : Promise.resolve({ results: [] as EnrollmentRow[] }),
      academicsApi.classSessions(row.class_id, row.site_code),
    ]);
    if (detailResult.status === "fulfilled") setDetail(detailResult.value);
    if (rosterResult.status === "fulfilled") setRoster(rosterResult.value.results);
    if (sessionResult.status === "fulfilled") setSessions(sessionResult.value.results);
  };
  const createClass = async (values: Record<string, string | number | number[]>) => {
    if (!actionSite) return;
    try {
      if (editingClass) {
        await academicsApi.updateClass(editingClass.class_id, editingClass.site_code, { name: String(values.name), capacity: Number(values.capacity) });
        message.success(`Đã cập nhật lớp tại ${editingClass.site_code}.`);
      } else {
        await academicsApi.createClass({ site_code: actionSite, course_id: String(values.course_id), teacher_id: String(values.teacher_id), room_id: String(values.room_id), name: String(values.name), capacity: Number(values.capacity), start_date: String(values.start_date), end_date: String(values.end_date), weekdays: values.weekdays as number[], start_time: String(values.start_time), end_time: String(values.end_time) });
        message.success(`Đã tạo lớp và lịch tại ${actionSite}.`);
      }
      setModal(null); setEditingClass(null); classForm.resetFields(); refreshAfterWrite(editingClass?.site_code || actionSite);
    } catch (error) { message.error(reason(error)); }
  };
  const editClass = (row: ClassRow) => {
    setOperationSite(row.site_code); setEditingClass(row); setModal("class");
  };
  useEffect(() => {
    if (modal === "class" && editingClass) classForm.setFieldsValue({ name: editingClass.name, capacity: editingClass.capacity });
  }, [classForm, editingClass, modal]);
  const removeClass = (row: ClassRow) => Modal.confirm({
    title: `Hủy lớp ${row.name}?`,
    content: "Chỉ hủy lớp sắp mở chưa có đăng ký và mọi buổi học đều ở tương lai, trạng thái dự kiến. Hồ sơ lớp, lịch học và nhật ký sẽ được giữ lại.",
    okText: "Hủy lớp", cancelText: "Quay lại", okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await academicsApi.deleteClass(row.class_id, row.site_code);
        message.success(`Đã hủy lớp ${row.name}.`); refreshAfterWrite(row.site_code);
      } catch (error) { message.error(reason(error)); }
    },
  });
  const enroll = async (values: { student_id: string; class_id: string }) => {
    if (!actionSite) return;
    try { await academicsApi.enroll({ site_code: actionSite, ...values }); message.success(`Đã đăng ký học tại ${actionSite}.`); setModal(null); simpleForm.resetFields(); refreshAfterWrite(actionSite); }
    catch (error) { message.error(reason(error)); }
  };
  const moveEnrollment = async (values: { enrollment_id: string; target_class_id: string }) => {
    if (!actionSite) return;
    try { await academicsApi.moveEnrollment(values.enrollment_id, actionSite, values.target_class_id); message.success(`Đã xếp lại lớp tại ${actionSite}.`); setModal(null); simpleForm.resetFields(); refreshAfterWrite(actionSite); }
    catch (error) { message.error(reason(error)); }
  };
  const assignTeacher = async (values: { teacher_id: string }) => {
    if (!detail) return;
    try { await academicsApi.assignTeacher(detail.class_id, detail.site_code, values.teacher_id); message.success(`Đã cập nhật giáo viên tại ${detail.site_code}.`); setModal(null); refreshAfterWrite(detail.site_code); void showClass(detail); }
    catch (error) { message.error(reason(error)); }
  };
  const columns = [
    { title: "Lớp", dataIndex: "name", render: (value: string, row: ClassRow) => <Button type="link" onClick={() => void showClass(row)}>{value}</Button> },
    { title: "Cơ sở", dataIndex: "site_code" }, { title: "Khóa học", dataIndex: "course_name" }, { title: "Giáo viên", dataIndex: "teacher_name" }, { title: "Phòng", dataIndex: "room_name" },
    { title: "Lịch", dataIndex: "schedule" }, { title: "Ngày", render: (_: unknown, row: ClassRow) => `${row.start_date} – ${row.end_date || "—"}` },
    { title: "Sĩ số", render: (_: unknown, row: ClassRow) => <span>{row.registered_count}/{row.capacity} · còn {row.remaining_seats}</span> },
    { title: "Trạng thái", dataIndex: "status", render: (value: string) => <Tag>{value}</Tag> },
    ...(canAdministerClasses ? [{ title: "Thao tác", render: (_: unknown, row: ClassRow) => row.status === "huy" ? null : <Space><Button size="small" onClick={() => editClass(row)}>Sửa</Button><Button size="small" danger onClick={() => removeClass(row)}>Hủy lớp</Button></Space> }] : []),
  ];
  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {!site && <Alert type="warning" showIcon title="Chưa có site được chọn hoặc phiên chưa trả phạm vi cơ sở." />}
    {error && <Alert type="error" showIcon title={error} />}
    {partial.length > 0 && <Alert type="warning" showIcon title={`Global Query thiếu site: ${partial.join(", ")}; dữ liệu chưa đầy đủ.`} />}
    <Card title={`Lớp học · ${site === ALL_SITES ? "Toàn hệ thống" : site || "Chưa chọn cơ sở"}`} extra={<Space wrap>{canEnroll && <Button disabled={!canStartOperation} onClick={() => openOperation("move")}>Chuyển lớp</Button>}{canEnroll && <Button disabled={!canStartOperation} onClick={() => openOperation("enroll")}>Đăng ký học</Button>}{canAdministerClasses && <Button type="primary" onClick={() => openOperation("class")} disabled={!canStartOperation}>Mở lớp</Button>}</Space>}>
      <Table rowKey="class_id" loading={loading} columns={columns} dataSource={classes} scroll={{ x: 1000 }} />
    </Card>
    <Modal title={editingClass ? "Sửa lớp" : "Tạo lớp và lịch"} open={modal === "class"} onCancel={() => { setModal(null); setEditingClass(null); classForm.resetFields(); }} footer={null} width={700} destroyOnHidden><Form form={classForm} layout="vertical" onFinish={createClass}>
      {operationSiteField}{operationAlert}
      <Form.Item name="name" label="Tên lớp" rules={[{ required: true }]}><Input maxLength={120} /></Form.Item>
      {editingClass ? <Form.Item name="capacity" label="Sĩ số tối đa" rules={[{ required: true }]}><InputNumber min={1} max={300} style={{ width: "100%" }} /></Form.Item> : <>
      <Form.Item name="course_id" label="Mã khóa học có sẵn tại site" rules={[{ required: true }]}><Input maxLength={30} /></Form.Item>
      <Form.Item name="teacher_id" label="Giáo viên" rules={[{ required: true }]}><Select loading={operationLoading} options={teachers.map((x) => ({ value: x.teacher_id, label: `${x.full_name} · ${x.teacher_id}` }))} /></Form.Item>
      <Form.Item name="room_id" label="Phòng" rules={[{ required: true }]}><Select loading={operationLoading} options={rooms.filter((x) => x.status === "hoat_dong").map((x) => ({ value: x.room_id, label: `${x.name} · tối đa ${x.capacity}` }))} /></Form.Item>
      <Form.Item name="capacity" label="Sĩ số tối đa" rules={[{ required: true }]}><InputNumber min={1} max={300} style={{ width: "100%" }} /></Form.Item>
      <Space wrap><Form.Item name="start_date" label="Ngày bắt đầu" rules={[{ required: true }]}><Input type="date" /></Form.Item><Form.Item name="end_date" label="Ngày kết thúc" rules={[{ required: true }]}><Input type="date" /></Form.Item><Form.Item name="start_time" label="Giờ bắt đầu" rules={[{ required: true }]}><Input type="time" /></Form.Item><Form.Item name="end_time" label="Giờ kết thúc" rules={[{ required: true }]}><Input type="time" /></Form.Item></Space>
      <Form.Item name="weekdays" label="Ngày học trong tuần" rules={[{ required: true }]}><Checkbox.Group options={weekdays} /></Form.Item>
      </>}
      <Button type="primary" htmlType="submit" block disabled={editingClass ? false : operationSubmitDisabled}>{editingClass ? "Lưu thay đổi" : "Tạo lớp"}</Button>
    </Form></Modal>
    <Modal title="Đăng ký học viên vào lớp" open={modal === "enroll"} onCancel={() => setModal(null)} footer={null}><Form form={simpleForm} layout="vertical" onFinish={enroll}>{operationSiteField}{operationAlert}<Form.Item name="student_id" label="Học viên" rules={[{ required: true }]}><Select showSearch optionFilterProp="label" loading={operationLoading} options={students.map((x) => ({ value: x.student_id, label: `${x.full_name} · ${x.student_id}` }))} /></Form.Item><Form.Item name="class_id" label="Lớp" rules={[{ required: true }]}><Select loading={operationLoading} options={operationClasses.map((x) => ({ value: x.class_id, label: `${x.name} · còn ${x.remaining_seats}` }))} /></Form.Item><Button type="primary" htmlType="submit" block disabled={operationSubmitDisabled}>Đăng ký</Button></Form></Modal>
    <Modal title="Chuyển đăng ký sang lớp khác" open={modal === "move"} onCancel={() => setModal(null)} footer={null} width={760}><Form form={simpleForm} layout="vertical" onFinish={moveEnrollment}>{operationSiteField}{operationAlert}<Form.Item name="source_class_id" label="Lớp hiện tại · phòng" rules={[{ required: true, message: "Chọn lớp hiện tại của học viên." }]}><Select showSearch optionFilterProp="label" loading={operationLoading} options={operationClasses.map((x) => ({ value: x.class_id, label: "Lớp " + x.name + " · Phòng " + (x.room_name || "Chưa xếp") + " · " + x.schedule }))} onChange={(value) => { setSourceClassId(value); setMoveEnrollments([]); setOperationError(""); simpleForm.setFieldsValue({ enrollment_id: undefined, target_class_id: undefined }); }} /></Form.Item><Form.Item name="enrollment_id" label="Học viên" rules={[{ required: true, message: "Chọn học viên cần chuyển lớp." }]}><Select showSearch optionFilterProp="label" loading={moveRosterLoading} disabled={!sourceClassId || moveRosterLoading} placeholder={sourceClassId ? "Tìm theo họ tên hoặc mã học viên" : "Chọn lớp hiện tại trước"} notFoundContent={moveRosterLoading ? "Đang tải học viên..." : "Lớp này không có đăng ký đang hiệu lực."} options={moveEnrollments.filter((x) => x.student_status === "dang_hoc").map((x) => ({ value: x.enrollment_id, label: x.full_name + " · " + x.student_id + " · " + x.enrollment_id }))} /></Form.Item><Form.Item name="target_class_id" label="Lớp đích · phòng" rules={[{ required: true, message: "Chọn lớp đích." }]}><Select showSearch optionFilterProp="label" loading={operationLoading} disabled={!sourceClassId} placeholder="Chọn lớp cùng khóa học còn chỗ" options={targetClasses.map((x) => ({ value: x.class_id, label: "Lớp " + x.name + " · Phòng " + (x.room_name || "Chưa xếp") + " · " + x.schedule + " · còn " + x.remaining_seats }))} /></Form.Item><Button type="primary" htmlType="submit" block disabled={operationSubmitDisabled}>Xếp lớp lại</Button></Form></Modal>
    <Modal title="Chi tiết lớp" open={Boolean(detail)} onCancel={() => setDetail(null)} footer={<Space>{canAdministerClasses && detail && (isAdminBig || site === detail.site_code) && <Button onClick={() => openOperation("teacher", detail.site_code)}>Đổi giáo viên</Button>}<Button onClick={() => setDetail(null)}>Đóng</Button></Space>} width={900}><Descriptions size="small" column={2} items={detail ? [{ key: "id", label: "Mã lớp", children: detail.class_id }, { key: "site", label: "Cơ sở", children: detail.site_code }, { key: "count", label: "Sĩ số", children: `${detail.registered_count}/${detail.capacity}` }, { key: "schedule", label: "Lịch", children: detail.schedule }] : []} /><Tabs items={[...(canViewRoster ? [{ key: "students", label: `Học viên (${roster.length})`, children: <Table rowKey="enrollment_id" size="small" dataSource={roster} columns={[{ title: "Tên", dataIndex: "full_name" }, { title: "Mã học viên", dataIndex: "student_id" }, { title: "Đăng ký", dataIndex: "enrollment_status" }]} /> }] : []), { key: "sessions", label: `Buổi học (${sessions.length})`, children: <Table rowKey="session_id" size="small" dataSource={sessions} columns={[{ title: "Buổi", dataIndex: "session_number" }, { title: "Ngày", dataIndex: "date" }, { title: "Giờ", render: (_: unknown, x: SessionRow) => `${x.start_time}–${x.end_time}` }, { title: "Phòng", dataIndex: "room_name" }, { title: "Trạng thái", dataIndex: "status" }]} /> }]} /></Modal>
    <Modal title="Phân công giáo viên" open={modal === "teacher"} onCancel={() => setModal(null)} footer={null}><Form layout="vertical" onFinish={assignTeacher}>{operationSiteField}{operationAlert}<Form.Item name="teacher_id" label="Giáo viên đang hoạt động" rules={[{ required: true }]}><Select loading={operationLoading} options={teachers.map((x) => ({ value: x.teacher_id, label: x.full_name }))} /></Form.Item><Button type="primary" htmlType="submit" block disabled={operationSubmitDisabled}>Lưu phân công</Button></Form></Modal>
  </Space>;
}

function reason(error: unknown) { return error instanceof Error ? error.message : "Yêu cầu API thất bại."; }
