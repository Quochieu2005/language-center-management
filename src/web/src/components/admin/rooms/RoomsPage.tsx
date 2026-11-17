"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Empty, Form, Input, InputNumber, Modal, Select, Space, Spin, Table, Tag, message } from "antd";
import { academicsApi, type RoomRosterClass, type RoomRosterStudent, type RoomRow } from "@/lib/api/academics";
import { useSession } from "@/lib/auth/session";
import { ALL_SITES, useSiteScope } from "@/lib/auth/site-scope";

type RoomFormValues = { site_code?: string; name: string; capacity: number; status: string };
const PAGE_SIZE = 25;
const money = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });

export default function RoomsPage() {
  const { user } = useSession();
  const { selectedSite, siteCodes, loadingSites } = useSiteScope();
  const isAdminBig = user?.role === "admin_big";
  const canManage = isAdminBig || user?.role === "admin_small" || user?.role === "tu_van";
  const canSendReminder = canManage || user?.role === "ke_toan" || user?.role === "tu_van";
  const site = isAdminBig ? selectedSite : user?.site_code || null;
  const global = isAdminBig && site === ALL_SITES;
  const [rooms, setRooms] = useState<RoomRow[]>([]);
  const [count, setCount] = useState<number | null>(0);
  const [missingSites, setMissingSites] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form] = Form.useForm<RoomFormValues>();
  const [editing, setEditing] = useState<RoomRow | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<RoomRow | null>(null);
  const [deleting, setDeleting] = useState(false);
  const canCreate = canManage && (isAdminBig ? !loadingSites && siteCodes.length > 0 : Boolean(site));

  const load = useCallback(async (isCurrent: () => boolean = () => true) => {
    if (!site || loadingSites) return;
    setLoading(true);
    setError("");
    try {
      const result = await academicsApi.rooms(global ? undefined : site, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      if (!isCurrent()) return;
      setRooms(result.results);
      setCount(result.count);
      setMissingSites(result.missing_sites || []);
    } catch (reason) {
      if (!isCurrent()) return;
      setRooms([]);
      setCount(0);
      setMissingSites([]);
      setError(errorMessage(reason));
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [global, loadingSites, page, site]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(() => !cancelled); });
    return () => { cancelled = true; };
  }, [load]);

  const refresh = () => {
    if (page !== 1) setPage(1);
    else void load();
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    if (!global && site) form.setFieldValue("site_code", site);
    form.setFieldValue("status", "hoat_dong");
    setFormOpen(true);
  };

  const openEdit = (room: RoomRow) => {
    setEditing(room);
    form.setFieldsValue({ name: room.name, capacity: room.capacity, status: room.status, site_code: room.site_code });
    setFormOpen(true);
  };

  const save = async (values: RoomFormValues) => {
    const targetSite = editing?.site_code || (global ? values.site_code : site);
    if (!targetSite) return;
    try {
      if (editing) {
        await academicsApi.updateRoom(editing.room_id, targetSite, {
          name: values.name.trim(), capacity: Number(values.capacity), status: values.status,
        });
        message.success("Đã cập nhật phòng học.");
      } else {
        await academicsApi.createRoom({ site_code: targetSite, name: values.name.trim(), capacity: Number(values.capacity) });
        message.success(`Đã tạo phòng học tại ${targetSite}.`);
      }
      setFormOpen(false);
      form.resetFields();
      refresh();
    } catch (reason) {
      message.error(errorMessage(reason));
    }
  };

  const remove = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await academicsApi.deleteRoom(deleteTarget.room_id, deleteTarget.site_code);
      message.success(`Đã xóa phòng ${deleteTarget.name}.`);
      setDeleteTarget(null);
      refresh();
    } catch (reason) {
      message.error(errorMessage(reason));
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    { title: "Mã phòng", dataIndex: "room_id" },
    { title: "Tên phòng", dataIndex: "name" },
    { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Sức chứa", dataIndex: "capacity", render: (value: number) => `${value} học viên` },
    { title: "Lớp đang mở", dataIndex: "class_count" },
    { title: "Học viên", dataIndex: "student_count" },
    { title: "Trạng thái", dataIndex: "status", render: (value: string) => <Tag color={value === "hoat_dong" ? "green" : "orange"}>{value === "hoat_dong" ? "Hoạt động" : "Bảo trì"}</Tag> },
    ...(canManage ? [{ title: "Thao tác", render: (_: unknown, row: RoomRow) => <Space><Button onClick={() => openEdit(row)}>Sửa</Button><Button danger onClick={() => setDeleteTarget(row)}>Xóa</Button></Space> }] : []),
  ];

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {!site && !loadingSites && <Alert type="warning" showIcon title="Chưa có site được chọn hoặc phiên chưa trả phạm vi cơ sở." />}
    {error && <Alert type="error" showIcon title={error} />}
    {missingSites.length > 0 && <Alert type="warning" showIcon title={`Global Query thiếu site: ${missingSites.join(", ")}; danh sách chưa đầy đủ.`} />}
    {!canManage && <Alert type="info" showIcon title="Bạn chỉ được xem phòng, lớp, danh sách học viên và tình trạng học phí tại cơ sở được phân công." />}
    <Card title={`${canManage ? "Quản lý phòng học" : "Phòng học"} · ${global ? "Toàn hệ thống" : site || "Chưa chọn cơ sở"}`} extra={<Space><Button onClick={() => void load()} loading={loading}>Tải lại</Button>{canManage && <Button type="primary" onClick={openCreate} disabled={!canCreate}>Thêm phòng</Button>}</Space>}>
      <Table
        rowKey={(row) => `${row.site_code}:${row.room_id}`}
        loading={loading || loadingSites}
        columns={columns}
        dataSource={rooms}
        scroll={{ x: 900 }}
        expandable={{ expandedRowRender: (room) => <RoomRosterPanel key={`${room.site_code}:${room.room_id}`} room={room} canSendReminder={canSendReminder} /> }}
        pagination={{ current: page, pageSize: PAGE_SIZE, total: count ?? rooms.length, showSizeChanger: false, onChange: setPage }}
      />
    </Card>

    <Modal title={editing ? "Sửa phòng học" : "Thêm phòng học"} open={formOpen} onCancel={() => setFormOpen(false)} onOk={() => form.submit()} okText={editing ? "Lưu thay đổi" : "Tạo phòng"} destroyOnHidden>
      <Form form={form} layout="vertical" onFinish={save}>
        {global && !editing && <Form.Item name="site_code" label="Cơ sở" rules={[{ required: true, message: "Chọn cơ sở cần thêm phòng." }]}><Select options={siteCodes.map((code) => ({ value: code, label: code }))} placeholder="Chọn cơ sở" /></Form.Item>}
        {(editing || !global) && <Form.Item label="Cơ sở"><Input value={editing?.site_code || site || ""} disabled /></Form.Item>}
        <Form.Item name="name" label="Tên phòng" rules={[{ required: true, whitespace: true, message: "Nhập tên phòng." }, { max: 100, message: "Tên phòng tối đa 100 ký tự." }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="capacity" label="Sức chứa" rules={[{ required: true, message: "Nhập sức chứa." }]}><InputNumber min={1} max={300} precision={0} style={{ width: "100%" }} /></Form.Item>
        {editing && <Form.Item name="status" label="Trạng thái" rules={[{ required: true }]}><Select options={[{ value: "hoat_dong", label: "Hoạt động" }, { value: "bao_tri", label: "Bảo trì" }]} /></Form.Item>}
      </Form>
    </Modal>

    <Modal title="Xóa phòng học này?" open={Boolean(deleteTarget)} onCancel={() => setDeleteTarget(null)} onOk={() => void remove()} confirmLoading={deleting} okText="Xóa phòng" cancelText="Hủy" okButtonProps={{ danger: true }}>
      Phòng {deleteTarget?.name} tại {deleteTarget?.site_code} sẽ bị xóa vĩnh viễn. Phòng đang được lớp hoặc buổi học sử dụng sẽ được API từ chối để giữ lịch sử.
    </Modal>
  </Space>;
}

function RoomRosterPanel({ room, canSendReminder }: { room: RoomRow; canSendReminder: boolean }) {
  const [classes, setClasses] = useState<RoomRosterClass[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sending, setSending] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    academicsApi.roomRoster(room.room_id, room.site_code)
      .then((result) => { if (!cancelled) setClasses(result.classes); })
      .catch((reason: unknown) => { if (!cancelled) setError(errorMessage(reason)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [room.room_id, room.site_code]);

  const remind = async (classItem: RoomRosterClass) => {
    setSending(classItem.class_id);
    try {
      const result = await academicsApi.sendTuitionReminders(classItem.class_id, room.site_code);
      const unpaid = Number(result.unpaid_students || 0);
      if (!unpaid) {
        message.info(`Lớp ${classItem.class_name} hiện không có học viên còn nợ.`);
      } else {
        message.success(`Lớp ${classItem.class_name}: đã gửi ${Number(result.sent_count || 0)}, đã nhắc hôm nay ${Number(result.already_sent_count || 0)}, thiếu email ${Number(result.missing_email_count || 0)}, lỗi gửi ${Number(result.failed_count || 0)}.`);
      }
    } catch (reason) {
      message.error(errorMessage(reason));
    } finally {
      setSending(null);
    }
  };

  if (loading) return <Spin />;
  if (error) return <Alert type="error" showIcon title={error} />;
  if (!classes.length) return <Empty description="Phòng chưa có lớp sắp mở hoặc đang học." />;

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {classes.map((classItem) => <Card
      key={classItem.class_id}
      size="small"
      title={`${classItem.class_name} · ${classItem.student_count} học viên`}
      extra={canSendReminder && <Button size="small" loading={sending === classItem.class_id} disabled={!classItem.students.some((student) => student.balance > 0)} onClick={() => void remind(classItem)}>Gửi email nhắc học phí</Button>}
    >
      <Table<RoomRosterStudent>
        size="small"
        rowKey="student_id"
        pagination={false}
        dataSource={classItem.students}
        locale={{ emptyText: "Chưa có học viên đang học." }}
        columns={[
          { title: "Học viên", dataIndex: "student_name" },
          { title: "Tình trạng học phí", dataIndex: "tuition_status", render: tuitionStatus },
          { title: "Phải đóng", dataIndex: "total_due", render: formatMoney },
          { title: "Đã đóng", dataIndex: "amount_paid", render: formatMoney },
          { title: "Còn nợ", dataIndex: "balance", render: formatMoney },
        ]}
        scroll={{ x: 720 }}
      />
    </Card>)}
  </Space>;
}

function tuitionStatus(value: RoomRosterStudent["tuition_status"]) {
  const labels = {
    chua_co_khoan_phi: ["Chưa có khoản phí", "default"],
    chua_dong: ["Chưa đóng", "red"],
    dong_mot_phan: ["Đóng một phần", "orange"],
    da_dong: ["Đã đóng", "green"],
  } as const;
  const [label, color] = labels[value] || labels.chua_co_khoan_phi;
  return <Tag color={color}>{label}</Tag>;
}

function formatMoney(value: number) { return `${money.format(value)} đ`; }
function errorMessage(error: unknown) { return error instanceof Error ? error.message : "Yêu cầu API thất bại."; }
