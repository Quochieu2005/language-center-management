"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, message } from "antd";
import { adminApi, type Teacher } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

export default function TeachersPage() {
  const { user } = useSession();
  const { siteCodes, selectedSite, setSelectedSite } = useSiteScope();
  const [rows, setRows] = useState<Teacher[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<Teacher | null>(null);
  const [form] = Form.useForm();
  const site = user?.role === "admin_big" ? selectedSite : user?.site_code || undefined;
  const load = useCallback(async () => {
    if (!site) return;
    try { const data = await adminApi.teachers(site, { limit: 100 }); setRows(data.results); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được danh sách giáo viên."); }
    finally { setLoading(false); }
  }, [site]);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);
  const columns = [
    { title: "Họ tên", dataIndex: "full_name", render: (value: string, row: Teacher) => <Button type="link" disabled={!row.slug} onClick={async () => { try { setDetail(await adminApi.teacher(row.slug!, row.site_code)); } catch (e) { message.error(e instanceof Error ? e.message : "Không tải được hồ sơ giáo viên."); } }}>{value}</Button> }, { title: "Email", dataIndex: "email" }, { title: "Điện thoại", dataIndex: "phone" },
    { title: "Chuyên môn", dataIndex: "specialty" }, { title: "Trạng thái tài khoản", dataIndex: "account_status", render: (value: string | null) => <Tag color={value === "active" ? "green" : "default"}>{value || "Chưa cấp"}</Tag> },
    { title: "Trạng thái hồ sơ", dataIndex: "status" },
    { title: "Thao tác", render: (_: unknown, row: Teacher) => <Space><Button size="small" disabled={!row.slug || !row.account_status} onClick={async () => { try { await adminApi.setTeacherStatus(row.slug!, row.site_code, row.account_status === "active" ? "inactive" : "active"); void load(); } catch (e) { message.error(e instanceof Error ? e.message : "Không đổi được trạng thái."); } }}>{row.account_status === "active" ? "Ngưng" : "Kích hoạt"}</Button><Popconfirm title="Vô hiệu hóa tài khoản và xử lý hồ sơ giáo viên?" onConfirm={async () => { if (!row.slug) return; try { await adminApi.deleteTeacher(row.slug, row.site_code); message.success("Đã xử lý yêu cầu xóa theo API."); void load(); } catch (e) { message.error(e instanceof Error ? e.message : "Không xóa được."); } }}><Button danger size="small" disabled={!row.slug}>Xóa</Button></Popconfirm></Space> },
  ];
  const create = async (values: Record<string, string>) => {
    try { await adminApi.createTeacher({ full_name: values.full_name, email: values.email, username: values.username, phone: values.phone, specialty: values.specialty, site_code: site || undefined }); message.success("Đã tạo hồ sơ và tài khoản giáo viên."); setOpen(false); form.resetFields(); void load(); }
    catch (reason) { message.error(reason instanceof Error ? reason.message : "Không tạo được giáo viên."); }
  };
  return <Card title="Quản lý giáo viên" extra={<Button type="primary" disabled={!site} onClick={() => setOpen(true)}>Tạo giáo viên</Button>}>
    {user?.role === "admin_big" && <Select value={site || undefined} onChange={setSelectedSite} options={siteCodes.map((value) => ({ value, label: value }))} style={{ width: 150, marginBottom: 16 }} />}
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    <Table rowKey="teacher_id" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 850 }} />
    <Modal title="Chi tiết hồ sơ giáo viên" open={Boolean(detail)} onCancel={() => setDetail(null)} footer={null}><pre style={{ whiteSpace: "pre-wrap", overflow: "auto" }}>{detail ? JSON.stringify(detail, null, 2) : ""}</pre></Modal>
    <Modal title="Tạo giáo viên" open={open} onCancel={() => setOpen(false)} footer={null} destroyOnClose><Form form={form} layout="vertical" onFinish={create}>
      <Form.Item name="full_name" label="Họ tên" rules={[{ required: true, max: 120 }]}><Input maxLength={120} /></Form.Item>
      <Form.Item name="email" label="Email" rules={[{ required: true, type: "email" }]}><Input maxLength={254} /></Form.Item>
      <Form.Item name="username" label="Tên đăng nhập"><Input maxLength={100} /></Form.Item>
      <Form.Item name="phone" label="Điện thoại"><Input maxLength={20} /></Form.Item>
      <Form.Item name="specialty" label="Chuyên môn" rules={[{ required: true, max: 120 }]}><Input maxLength={120} /></Form.Item>
      <Button type="primary" htmlType="submit" block>Tạo tài khoản và gửi thông tin cấp</Button>
    </Form></Modal>
  </Card>;
}
