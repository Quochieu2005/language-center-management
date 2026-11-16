"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, message } from "antd";
import { academicsApi, type RoomRow } from "@/lib/api/academics";
import { useSession } from "@/lib/auth/session";
import { ALL_SITES, useSiteScope } from "@/lib/auth/site-scope";

type RoomFormValues = { site_code?: string; name: string; capacity: number; status: string };
const PAGE_SIZE = 25;

export default function RoomsPage() {
  const { user } = useSession();
  const { selectedSite, siteCodes, loadingSites } = useSiteScope();
  const isAdminBig = user?.role === "admin_big";
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
  const canCreate = isAdminBig ? !loadingSites && siteCodes.length > 0 : Boolean(site);

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
    { title: "Trạng thái", dataIndex: "status", render: (value: string) => <Tag color={value === "hoat_dong" ? "green" : "orange"}>{value === "hoat_dong" ? "Hoạt động" : "Bảo trì"}</Tag> },
    { title: "Thao tác", render: (_: unknown, row: RoomRow) => <Space><Button onClick={() => openEdit(row)}>Sửa</Button><Button danger onClick={() => setDeleteTarget(row)}>Xóa</Button></Space> },
  ];

  return <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
    {!site && !loadingSites && <Alert type="warning" showIcon title="Chưa có site được chọn hoặc phiên chưa trả phạm vi cơ sở." />}
    {error && <Alert type="error" showIcon title={error} />}
    {missingSites.length > 0 && <Alert type="warning" showIcon title={`Global Query thiếu site: ${missingSites.join(", ")}; danh sách chưa đầy đủ.`} />}
    <Card title={`Quản lý phòng học · ${global ? "Toàn hệ thống" : site || "Chưa chọn cơ sở"}`} extra={<Space><Button onClick={() => void load()} loading={loading}>Tải lại</Button><Button type="primary" onClick={openCreate} disabled={!canCreate}>Thêm phòng</Button></Space>}>
      <Table
        rowKey="room_id"
        loading={loading || loadingSites}
        columns={columns}
        dataSource={rooms}
        scroll={{ x: 800 }}
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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Yêu cầu API thất bại.";
}
