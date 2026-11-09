"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { adminApi, type AdminSmall, type Employee } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

type AccountsPageProps = { view: "admin-smalls" | "employees" };

export default function AccountsPage({ view }: AccountsPageProps) {
  const { user } = useSession();
  const { siteCodes, selectedSite } = useSiteScope();
  const [admins, setAdmins] = useState<AdminSmall[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();
  const isEmployeeView = view === "employees";
  const isAdminBig = user?.role === "admin_big";
  const site = isAdminBig ? selectedSite || undefined : user?.site_code || undefined;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (isEmployeeView) {
        if (!site) {
          setEmployees([]);
          setError("Chọn cơ sở để tải danh sách nhân viên.");
          return;
        }
        const result = await adminApi.employees(site);
        setEmployees(result.results);
      } else {
        const result = await adminApi.adminSmalls();
        setAdmins(result.results);
        if (!result.complete) setError(`Danh sách chưa đầy đủ; thiếu site: ${result.missing_sites.join(", ")}`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được dữ liệu.");
      if (reason instanceof ApiError && isEmployeeView && Array.isArray(reason.payload.results)) {
        setEmployees(reason.payload.results as Employee[]);
      }
    } finally {
      setLoading(false);
    }
  }, [isEmployeeView, site]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const submit = async (values: { full_name: string; email: string; username?: string; phone?: string; site_code?: string; job_title?: Employee["job_title"] }) => {
    try {
      if (isEmployeeView && values.job_title) {
        await adminApi.createEmployee({
          site_code: isAdminBig ? values.site_code : undefined,
          full_name: values.full_name,
          email: values.email,
          username: values.username,
          phone: values.phone,
          job_title: values.job_title,
        });
        message.success("Đã tạo tài khoản nhân viên theo phản hồi của API.");
      } else if (!isEmployeeView && values.site_code) {
        await adminApi.createAdminSmall({ full_name: values.full_name, email: values.email, username: values.username, site_code: values.site_code });
        message.success("Đã tạo Admin Small theo phản hồi của API.");
      }
      form.resetFields();
      setCreating(false);
      void load();
    } catch (reason) {
      message.error(reason instanceof ApiError ? reason.message : "Không tạo được tài khoản.");
    }
  };

  const adminColumns: ColumnsType<AdminSmall> = [
    { title: "Tên", dataIndex: "full_name" },
    { title: "Email", dataIndex: "email" },
    { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Trạng thái", dataIndex: "account_status", render: (value: string) => <Tag color={value === "active" ? "green" : "default"}>{value}</Tag> },
    {
      title: "Thao tác",
      render: (_: unknown, row: AdminSmall) => <Space>
        <Button size="small" onClick={async () => {
          const nextStatus = row.account_status === "active" ? "inactive" : "active";
          try {
            await adminApi.updateAdminSmallStatus(row.slug, nextStatus);
            message.success(nextStatus === "active" ? "Đã kích hoạt Admin Small." : "Đã ngưng tài khoản Admin Small.");
            void load();
          } catch (reason) { message.error(reason instanceof Error ? reason.message : "Không cập nhật được trạng thái."); }
        }}>{row.account_status === "active" ? "Ngưng" : "Kích hoạt"}</Button>
        <Popconfirm title="Vô hiệu hóa Admin Small?" onConfirm={async () => {
          try { await adminApi.deactivateAdminSmall(row.account_id); message.success("Đã vô hiệu hóa tài khoản."); void load(); }
          catch (reason) { message.error(reason instanceof Error ? reason.message : "Không vô hiệu hóa được tài khoản."); }
        }}><Button danger size="small">Xóa</Button></Popconfirm>
      </Space>,
    },
  ];

  const employeeColumns: ColumnsType<Employee> = [
    { title: "Tên", dataIndex: "full_name" },
    { title: "Email", dataIndex: "email" },
    { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Chức vụ", dataIndex: "job_title" },
    { title: "Trạng thái", dataIndex: "account_status", render: (value: string) => <Tag color={value === "active" ? "green" : "default"}>{value}</Tag> },
    {
      title: "Thao tác",
      render: (_: unknown, row: Employee) => <Popconfirm title="Vô hiệu hóa tài khoản nhân viên này?" onConfirm={async () => {
        try { await adminApi.deleteEmployee(row.slug, row.site_code); message.success("Đã vô hiệu hóa tài khoản."); void load(); }
        catch (reason) { message.error(reason instanceof Error ? reason.message : "Không vô hiệu hóa được tài khoản."); }
      }}><Button danger size="small">Xóa</Button></Popconfirm>,
    },
  ];

  return <Card
    title={isEmployeeView ? "Quản lý nhân viên" : "Quản trị Admin Small"}
    extra={<Button type="primary" onClick={() => { form.resetFields(); setCreating(true); }}>{isEmployeeView ? "Tạo nhân viên" : "Tạo Admin Small"}</Button>}
  >
    {error && <Alert type="warning" showIcon title={error} style={{ marginBottom: 16 }} />}
    {isEmployeeView
      ? <Table<Employee> rowKey="employee_id" loading={loading} columns={employeeColumns} dataSource={employees} scroll={{ x: 760 }} />
      : <Table<AdminSmall> rowKey="account_id" loading={loading} columns={adminColumns} dataSource={admins} scroll={{ x: 760 }} />}
    <Modal title={isEmployeeView ? "Tạo nhân viên" : "Tạo Admin Small"} open={creating} onCancel={() => setCreating(false)} footer={null} destroyOnHidden>
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item name="full_name" label="Họ tên" rules={[{ required: true, max: 120 }]}><Input maxLength={120} /></Form.Item>
        <Form.Item name="email" label="Email" rules={[{ required: true, type: "email" }]}><Input maxLength={254} /></Form.Item>
        <Form.Item name="username" label="Tên đăng nhập"><Input maxLength={100} /></Form.Item>
        {isEmployeeView && <Form.Item name="phone" label="Số điện thoại"><Input maxLength={20} /></Form.Item>}
        {isAdminBig && <Form.Item name="site_code" label="Cơ sở" rules={[{ required: true }]}><Select options={siteCodes.map((value) => ({ value, label: value }))} /></Form.Item>}
        {isEmployeeView && <Form.Item name="job_title" label="Chức vụ" rules={[{ required: true }]}><Select options={[
          { value: "le_tan", label: "Lễ tân" },
          { value: "tu_van", label: "Tư vấn" },
          { value: "ke_toan", label: "Kế toán" },
          { value: "xep_lop", label: "Xếp lớp" },
        ]} /></Form.Item>}
        <Button type="primary" htmlType="submit" block>Tạo tài khoản</Button>
      </Form>
    </Modal>
  </Card>;
}
