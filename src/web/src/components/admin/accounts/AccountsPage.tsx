"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { UploadOutlined, UserOutlined } from "@ant-design/icons";
import { Alert, App, Avatar, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { adminApi, type AdminSmall, type Employee } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

type AccountsPageProps = { view: "admin-smalls" | "employees" };

function toSlug(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[đĐ]/g, "d")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 120);
}

export default function AccountsPage({ view }: AccountsPageProps) {
  const { message, modal } = App.useApp();
  const { user } = useSession();
  const { siteCodes, selectedSite } = useSiteScope();
  const [admins, setAdmins] = useState<AdminSmall[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [deletingAdminSmall, setDeletingAdminSmall] = useState<AdminSmall | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sendingCredentialId, setSendingCredentialId] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState("");
  const [form] = Form.useForm();
  const avatarInput = useRef<HTMLInputElement>(null);
  const slugManuallyEdited = useRef(false);
  const isEmployeeView = view === "employees";
  const isAdminBig = user?.role === "admin_big";
  const site = isAdminBig ? selectedSite || undefined : user?.site_code || undefined;

  useEffect(() => {
    if (!avatarPreview) return;
    return () => URL.revokeObjectURL(avatarPreview);
  }, [avatarPreview]);

  const resetCreateForm = () => {
    slugManuallyEdited.current = false;
    form.resetFields();
    setAvatarFile(null);
    setAvatarPreview("");
    if (avatarInput.current) avatarInput.current.value = "";
  };

  const chooseAvatar = (file?: File) => {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      message.error("Chỉ nhận ảnh JPG, PNG hoặc WebP.");
      return;
    }
    if (file.size < 1 || file.size > 5 * 1024 * 1024) {
      message.error("Ảnh phải có dung lượng từ 1 byte đến 5 MB.");
      return;
    }
    setAvatarPreview(URL.createObjectURL(file));
    setAvatarFile(file);
  };

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

  const submit = async (values: { full_name: string; email: string; username?: string; slug?: string; phone?: string; site_code?: string; job_title?: Employee["job_title"] }) => {
    setSubmitting(true);
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
        const createdAccount = await adminApi.createAdminSmall({
          full_name: values.full_name,
          email: values.email,
          username: values.username,
          slug: values.slug || undefined,
          site_code: values.site_code,
          avatar_requested: Boolean(avatarFile),
        });
        if (avatarFile) {
          try {
            if (!createdAccount.avatar_setup_token) throw new Error("API không cấp quyền tải ảnh ban đầu.");
            const intent = await adminApi.createAdminSmallAvatarUploadIntent(createdAccount.slug, createdAccount.avatar_setup_token);
            const body = new FormData();
            body.append("file", avatarFile);
            body.append("api_key", intent.api_key);
            Object.entries(intent.fields).forEach(([key, value]) => body.append(key, value));
            const upload = await fetch(intent.upload_url, { method: "POST", body, cache: "no-store" });
            const uploaded = await upload.json().catch(() => null) as { public_id?: unknown } | null;
            if (!upload.ok || typeof uploaded?.public_id !== "string") {
              throw new Error("Cloudinary chưa nhận được ảnh.");
            }
            await adminApi.completeAdminSmallAvatarUpload(createdAccount.slug, {
              setup_token: createdAccount.avatar_setup_token,
              intent_token: intent.intent_token,
              public_id: uploaded.public_id,
            });
            message.success("Đã tạo Admin Small và tải ảnh đại diện lên.");
          } catch (reason) {
            const detail = reason instanceof Error ? reason.message : "Lỗi tải ảnh không xác định.";
            message.warning(`Đã tạo tài khoản Admin Small nhưng ảnh chưa được lưu: ${detail}. Có thể thêm ảnh sau trong hồ sơ.`);
          }
        }
        message.success(createdAccount.credential_email_status === "ready"
          ? "Đã tạo Admin Small. Bấm Gửi mật khẩu trong danh sách để gửi email một lần."
          : "Tài khoản đã tồn tại từ lần tạo trước; trạng thái email không rõ nên hệ thống khóa gửi lại.");
      }
      resetCreateForm();
      setCreating(false);
      void load();
    } catch (reason) {
      message.error(reason instanceof ApiError ? reason.message : "Không tạo được tài khoản.");
    } finally {
      setSubmitting(false);
    }
  };

  const confirmDeleteAdminSmall = async () => {
    if (!deletingAdminSmall) return;
    setDeleteSubmitting(true);
    try {
      await adminApi.deleteAdminSmall(deletingAdminSmall.account_id);
      message.success("Đã xóa vĩnh viễn Admin Small.");
      setDeletingAdminSmall(null);
      void load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không xóa được Admin Small; hãy thử lại.");
    } finally {
      setDeleteSubmitting(false);
    }
  };

  const adminColumns: ColumnsType<AdminSmall> = [
    { title: "Tên", dataIndex: "full_name" },
    { title: "Email", dataIndex: "email" },
    { title: "Cơ sở", dataIndex: "site_code" },
    {
      title: "Mật khẩu qua email",
      dataIndex: "credential_email_status",
      render: (value: AdminSmall["credential_email_status"], row: AdminSmall) => {
        if (value === "ready" || value === "failed") {
          return <Popconfirm
            title={value === "failed" ? "Thử gửi lại mật khẩu?" : "Gửi mật khẩu tạm một lần?"}
            description={`Email sẽ được gửi đến ${row.email}. Sau khi gửi thành công, không thể gửi lại.`}
            onConfirm={async () => {
              setSendingCredentialId(row.account_id);
              try {
                await adminApi.sendAdminSmallCredentials(row.account_id);
                message.success(`Đã gửi mật khẩu đến ${row.email}. Không thể gửi lại.`);
                await load();
              } catch (reason) {
                message.error(reason instanceof Error ? reason.message : "Không gửi được email.");
                void load();
              } finally { setSendingCredentialId(""); }
            }}
          >
            <Button size="small" type="primary" loading={sendingCredentialId === row.account_id} disabled={row.account_status !== "active"}>
              {value === "failed" ? "Thử lại" : "Gửi mật khẩu"}
            </Button>
          </Popconfirm>;
        }
        const labels: Record<Exclude<AdminSmall["credential_email_status"], "ready" | "failed">, [string, string]> = {
          sent: ["Đã gửi", "green"],
          processing: ["Đang xử lý", "processing"],
          unknown: ["Không rõ · đã khóa gửi lại", "default"],
          changed: ["Mật khẩu đã đổi", "default"],
        };
        const [label, color] = labels[value];
        return <Tag color={color}>{label}</Tag>;
      },
    },
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
        <Button danger size="small" onClick={() => setDeletingAdminSmall(row)}>Xóa vĩnh viễn</Button>
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
      render: (_: unknown, row: Employee) => <Button danger size="small" onClick={() => modal.confirm({ title: "Vô hiệu hóa tài khoản nhân viên này?", okText: "Xóa", cancelText: "Hủy", okButtonProps: { danger: true }, onOk: async () => {
        try { await adminApi.deleteEmployee(row.slug, row.site_code); message.success("Đã vô hiệu hóa tài khoản."); void load(); }
        catch (reason) { message.error(reason instanceof Error ? reason.message : "Không vô hiệu hóa được tài khoản."); }
      } })}>Xóa</Button>,
    },
  ];

  return <Card
    title={isEmployeeView ? "Quản lý nhân viên" : "Quản trị Admin Small"}
    extra={<Button type="primary" onClick={() => setCreating(true)}>{isEmployeeView ? "Tạo nhân viên" : "Tạo Admin Small"}</Button>}
  >
    {error && <Alert type="warning" showIcon title={error} style={{ marginBottom: 16 }} />}
    {isEmployeeView
      ? <Table<Employee> rowKey="employee_id" loading={loading} columns={employeeColumns} dataSource={employees} scroll={{ x: 760 }} />
      : <Table<AdminSmall> rowKey="account_id" loading={loading} columns={adminColumns} dataSource={admins} scroll={{ x: 760 }} />}
    <Modal title={isEmployeeView ? "Tạo nhân viên" : "Tạo Admin Small"} open={creating} onCancel={() => { if (!submitting) { setCreating(false); resetCreateForm(); } }} footer={null} destroyOnHidden closable={!submitting} mask={{ closable: !submitting }} keyboard={!submitting}>
      <Form form={form} layout="vertical" onFinish={submit}>
        {!isEmployeeView && <Form.Item label="Ảnh đại diện (không bắt buộc)">
          <Space align="center">
            <Avatar size={56} src={avatarPreview || undefined} icon={<UserOutlined />} alt="Ảnh đại diện Admin Small" />
            <Space orientation="vertical" size={4}>
              <input ref={avatarInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => { chooseAvatar(event.target.files?.[0]); event.currentTarget.value = ""; }} />
              <Button icon={<UploadOutlined />} onClick={() => avatarInput.current?.click()}>Chọn ảnh</Button>
              <Typography.Text type="secondary">JPG, PNG hoặc WebP · tối đa 5 MB</Typography.Text>
            </Space>
          </Space>
          {avatarFile && <Typography.Text type="secondary" style={{ display: "block", marginTop: 8 }}>{avatarFile.name}</Typography.Text>}
        </Form.Item>}
        <Form.Item name="full_name" label="Họ tên" rules={[{ required: true, max: 120 }]}><Input maxLength={120} onChange={(event) => {
          if (!isEmployeeView && !slugManuallyEdited.current) form.setFieldValue("slug", toSlug(event.target.value));
        }} /></Form.Item>
        <Form.Item name="email" label="Email" rules={[{ required: true, type: "email" }]}><Input maxLength={254} /></Form.Item>
        <Form.Item name="username" label="Tên đăng nhập"><Input maxLength={100} /></Form.Item>
        {!isEmployeeView && <Form.Item name="slug" label="Slug hồ sơ" extra="Tự tạo theo họ tên; bạn có thể tự sửa." rules={[{ pattern: /^[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*$/, message: "Slug chỉ gồm chữ không dấu, số và dấu gạch ngang." }, { max: 120 }]}><Input maxLength={120} onChange={(event) => {
          const slug = event.target.value;
          slugManuallyEdited.current = Boolean(slug);
          if (!slug) form.setFieldValue("slug", toSlug(form.getFieldValue("full_name") || ""));
        }} /></Form.Item>}
        {isEmployeeView && <Form.Item name="phone" label="Số điện thoại"><Input maxLength={20} /></Form.Item>}
        {isAdminBig && <Form.Item name="site_code" label="Cơ sở" rules={[{ required: true }]}><Select options={siteCodes.map((value) => ({ value, label: value }))} /></Form.Item>}
        {isEmployeeView && <Form.Item name="job_title" label="Chức vụ" rules={[{ required: true }]}><Select options={[
          { value: "le_tan", label: "Lễ tân" },
          { value: "tu_van", label: "Tư vấn" },
          { value: "ke_toan", label: "Kế toán" },
          { value: "xep_lop", label: "Xếp lớp" },
        ]} /></Form.Item>}
        <Button type="primary" htmlType="submit" loading={submitting} block>Tạo tài khoản</Button>
      </Form>
    </Modal>
    <Modal
      title="Xóa vĩnh viễn Admin Small?"
      open={deletingAdminSmall !== null}
      centered
      width={460}
      okText="Xóa vĩnh viễn"
      cancelText="Hủy"
      okButtonProps={{ danger: true }}
      confirmLoading={deleteSubmitting}
      closable={!deleteSubmitting}
      mask={{ closable: !deleteSubmitting }}
      keyboard={!deleteSubmitting}
      onCancel={() => { if (!deleteSubmitting) setDeletingAdminSmall(null); }}
      onOk={confirmDeleteAdminSmall}
    >
      <Space orientation="vertical" size={8}>
        <Typography.Text>
          Xóa tài khoản, hồ sơ, phiên đăng nhập và ảnh đại diện của <strong>{deletingAdminSmall?.full_name}</strong>?
          Thao tác này không thể hoàn tác.
        </Typography.Text>
        <Typography.Text type="secondary">
          Nhật ký và lịch sử liên quan vẫn được giữ. Hệ thống sẽ từ chối nếu tài khoản còn dữ liệu nghiệp vụ cần bảo toàn.
        </Typography.Text>
      </Space>
    </Modal>
  </Card>;
}
