"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tabs, Tag, message } from "antd";
import { adminApi, type AdminSmall, type Employee } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

export default function AccountsPage() {
  const { user } = useSession();
  const { siteCodes, selectedSite } = useSiteScope();
  const [admins, setAdmins] = useState<AdminSmall[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState<"admin" | "employee" | null>(null);
  const [form] = Form.useForm();
  const site = user?.role === "admin_big" ? selectedSite || undefined : user?.site_code || undefined;
  const load = useCallback(async () => {
    const [adminResult, employeeResult] = await Promise.allSettled([
      user?.role === "admin_big" ? adminApi.adminSmalls() : Promise.resolve({ results: [] as AdminSmall[], complete: true, missing_sites: [] as string[], site_codes: [] as string[] }),
      site ? adminApi.employees(site) : Promise.resolve({ results: [] as Employee[] }),
    ]);
    if (adminResult.status === "fulfilled") {
      setAdmins(adminResult.value.results);
      if (!adminResult.value.complete) setError(`Danh sách Admin Small chưa đầy đủ; thiếu site: ${adminResult.value.missing_sites.join(", ")}`);
    } else {
      setError(adminResult.reason instanceof Error ? adminResult.reason.message : "Không tải được Admin Small.");
      if (adminResult.reason instanceof ApiError && Array.isArray(adminResult.reason.payload.results)) {
        const partial = adminResult.reason.payload.results.filter((item): item is AdminSmall => Boolean(item) && typeof item === "object");
        setAdmins(partial);
      }
    }
    if (employeeResult.status === "fulfilled") setEmployees(employeeResult.value.results);
    else setError((prev) => [prev, employeeResult.reason instanceof Error ? employeeResult.reason.message : "Không tải được nhân viên."].filter(Boolean).join(" · "));
    const failures = [adminResult.status === "rejected" ? adminResult.reason : null, employeeResult.status === "rejected" ? employeeResult.reason : null].filter(Boolean);
    if (failures.length) setError(failures.map((value) => value instanceof Error ? value.message : "Không tải được dữ liệu.").join(" · "));
    setLoading(false);
  }, [site, user?.role]);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);
  const submit = async (values: { full_name: string; email: string; username?: string; phone?: string; site_code?: string; job_title?: Employee["job_title"] }) => {
    try {
      if (creating === "admin") await adminApi.createAdminSmall({ full_name: values.full_name, email: values.email, username: values.username, site_code: values.site_code || site || "" });
      else if (creating === "employee" && values.job_title) await adminApi.createEmployee({ full_name: values.full_name, email: values.email, username: values.username, phone: values.phone, site_code: values.site_code || site, job_title: values.job_title });
      message.success("Đã tạo tài khoản theo phản hồi của API."); form.resetFields(); setCreating(null); void load();
    } catch (reason) { message.error(reason instanceof ApiError ? reason.message : "Không tạo được tài khoản."); }
  };
  const adminColumns = [
    { title: "Tên", dataIndex: "full_name" }, { title: "Email", dataIndex: "email" }, { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Trạng thái", dataIndex: "account_status", render: (v: string) => <Tag color={v === "active" ? "green" : "default"}>{v}</Tag> },
    { title: "Thao tác", render: (_: unknown, row: AdminSmall) => <Space><Button size="small" onClick={async () => { try { await adminApi.updateAdminSmallStatus(row.slug, row.account_status === "active" ? "inactive" : "active"); void load(); } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi cập nhật"); } }}>{row.account_status === "active" ? "Ngưng" : "Kích hoạt"}</Button><Popconfirm title="Vô hiệu hóa Admin Small?" onConfirm={async () => { try { await adminApi.deactivateAdminSmall(row.account_id); message.success("Đã vô hiệu hóa tài khoản."); void load(); } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi thao tác"); } }}><Button danger size="small">Xóa</Button></Popconfirm></Space> },
  ];
  const employeeColumns = [
    { title: "Tên", dataIndex: "full_name" }, { title: "Email", dataIndex: "email" }, { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Chức vụ", dataIndex: "job_title" }, { title: "Trạng thái", dataIndex: "account_status", render: (v: string) => <Tag color={v === "active" ? "green" : "default"}>{v}</Tag> },
    { title: "Thao tác", render: (_: unknown, row: Employee) => <Popconfirm title="Vô hiệu hóa tài khoản nhân viên này?" onConfirm={async () => { try { await adminApi.deleteEmployee(row.slug, row.site_code); message.success("Đã vô hiệu hóa tài khoản."); void load(); } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi thao tác"); } }}><Button danger size="small">Xóa</Button></Popconfirm> },
  ];
  return <Space direction="vertical" size="middle" style={{ width: "100%" }}>
    <Card title="Quản lý tài khoản và nhân viên" extra={<Space>{user?.role === "admin_big" && <Button onClick={() => { setCreating("admin"); form.resetFields(); }}>Tạo Admin Small</Button>}<Button type="primary" onClick={() => { setCreating("employee"); form.resetFields(); }}>Tạo nhân viên</Button></Space>}>
      {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
      {user?.role === "admin_big" && <Tabs items={[{ key: "admins", label: "Admin Small", children: <Table rowKey="account_id" loading={loading} columns={adminColumns} dataSource={admins} scroll={{ x: 700 }} /> }, { key: "employees", label: "Nhân viên", children: <Table rowKey="employee_id" loading={loading} columns={employeeColumns} dataSource={employees} scroll={{ x: 700 }} /> }]} />}
      {user?.role !== "admin_big" && <Table rowKey="employee_id" loading={loading} columns={employeeColumns} dataSource={employees} scroll={{ x: 700 }} />}
    </Card>
    <Modal title={creating === "admin" ? "Tạo Admin Small" : "Tạo nhân viên"} open={Boolean(creating)} onCancel={() => setCreating(null)} footer={null} destroyOnClose>
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item name="full_name" label="Họ tên" rules={[{ required: true, max: 120 }]}><Input maxLength={120} /></Form.Item>
        <Form.Item name="email" label="Email" rules={[{ required: true, type: "email" }]}><Input maxLength={254} /></Form.Item>
        <Form.Item name="username" label="Tên đăng nhập"><Input maxLength={100} /></Form.Item>
        <Form.Item name="phone" label="Số điện thoại"><Input maxLength={20} /></Form.Item>
        {user?.role === "admin_big" && <Form.Item name="site_code" label="Cơ sở" rules={[{ required: true }]}><Select options={siteCodes.map((value) => ({ value, label: value }))} /></Form.Item>}
        {creating === "employee" && <Form.Item name="job_title" label="Chức vụ" rules={[{ required: true }]}><Select options={[{ value: "le_tan", label: "Lễ tân" }, { value: "tu_van", label: "Tư vấn" }, { value: "ke_toan", label: "Kế toán" }, { value: "xep_lop", label: "Xếp lớp" }]} /></Form.Item>}
        <Button type="primary" htmlType="submit" block>Tạo tài khoản</Button>
      </Form>
    </Modal>
  </Space>;
}
