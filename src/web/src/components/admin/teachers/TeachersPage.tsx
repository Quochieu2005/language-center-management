"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { UploadOutlined, UserOutlined } from "@ant-design/icons";
import { Alert, App, Avatar, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { adminApi, type Teacher } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

type PendingTeacherAvatarSync = {
  slug: string;
  setupToken: string;
  intentToken: string;
  publicId: string;
  fullName: string;
};

const teacherSlug = (value: string) => value.toLowerCase().replace(/đ/g, "d").normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

export default function TeachersPage() {
  const { message, modal } = App.useApp();
  const { user } = useSession();
  const { siteCodes, selectedSite, setSelectedSite } = useSiteScope();
  const [rows, setRows] = useState<Teacher[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sendingCredentials, setSendingCredentials] = useState("");
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<Teacher | null>(null);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState("");
  const [pendingAvatarSync, setPendingAvatarSync] = useState<PendingTeacherAvatarSync | null>(null);
  const [retryingAvatarSync, setRetryingAvatarSync] = useState(false);
  const avatarInput = useRef<HTMLInputElement>(null);
  const slugEdited = useRef(false);
  const [form] = Form.useForm();
  const site = user?.role === "admin_big" ? selectedSite : user?.site_code || undefined;

  useEffect(() => {
    if (!avatarPreview) return;
    return () => URL.revokeObjectURL(avatarPreview);
  }, [avatarPreview]);

  const resetCreateForm = () => {
    form.resetFields();
    slugEdited.current = false;
    setAvatarFile(null);
    setAvatarPreview("");
    if (avatarInput.current) avatarInput.current.value = "";
  };

  const openCreateForm = () => {
    slugEdited.current = false;
    form.resetFields();
    form.setFieldsValue({ site_code: site || siteCodes[0], slug: "" });
    setAvatarFile(null);
    setAvatarPreview("");
    setOpen(true);
  };

  const retryAvatarSync = async () => {
    if (!pendingAvatarSync) return;
    setRetryingAvatarSync(true);
    try {
      await adminApi.completeTeacherAvatarUpload(pendingAvatarSync.slug, {
        setup_token: pendingAvatarSync.setupToken,
        intent_token: pendingAvatarSync.intentToken,
        public_id: pendingAvatarSync.publicId,
      });
      setPendingAvatarSync(null);
      message.success(`Đã đồng bộ ảnh đại diện cho ${pendingAvatarSync.fullName}.`);
      void load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Chưa đồng bộ được ảnh; hãy thử lại.");
    } finally {
      setRetryingAvatarSync(false);
    }
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
    if (!site) return;
    setLoading(true);
    try {
      const data = await adminApi.teachers(site, { limit: 100 });
      setRows(data.results);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được danh sách giáo viên.");
    } finally {
      setLoading(false);
    }
  }, [site]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const create = async (values: { full_name: string; email: string; username?: string; slug?: string; phone?: string; site_code?: string }) => {
    setSubmitting(true);
    try {
      const targetSite = user?.role === "admin_big" ? values.site_code : site;
      if (!targetSite) throw new Error("Vui lòng chọn cơ sở.");
      const created = await adminApi.createTeacher({
        full_name: values.full_name,
        email: values.email,
        username: values.username || undefined,
        slug: values.slug || undefined,
        phone: values.phone || undefined,
        avatar_requested: Boolean(avatarFile),
        site_code: user?.role === "admin_big" ? targetSite : undefined,
      });
      if (user?.role === "admin_big" && created.site_code !== site) setSelectedSite(created.site_code);
      if (avatarFile) {
        let retryData: PendingTeacherAvatarSync | null = null;
        try {
          if (!created.avatar_setup_token || !created.slug) throw new Error("API không cấp quyền tải ảnh ban đầu.");
          const intent = await adminApi.createTeacherAvatarUploadIntent(created.slug, created.avatar_setup_token);
          const body = new FormData();
          body.append("file", avatarFile);
          body.append("api_key", intent.api_key);
          Object.entries(intent.fields).forEach(([key, value]) => body.append(key, value));
          const upload = await fetch(intent.upload_url, { method: "POST", body, cache: "no-store" });
          const uploaded = await upload.json().catch(() => null) as { public_id?: unknown } | null;
          if (!upload.ok || typeof uploaded?.public_id !== "string") throw new Error("Cloudinary chưa nhận được ảnh.");
          retryData = {
            slug: created.slug,
            setupToken: created.avatar_setup_token,
            intentToken: intent.intent_token,
            publicId: uploaded.public_id,
            fullName: values.full_name,
          };
          setPendingAvatarSync(retryData);
          await adminApi.completeTeacherAvatarUpload(created.slug, {
            setup_token: created.avatar_setup_token,
            intent_token: intent.intent_token,
            public_id: uploaded.public_id,
          });
          setPendingAvatarSync(null);
          message.success("Đã tạo giáo viên và lưu ảnh đại diện.");
        } catch (reason) {
          const detail = reason instanceof Error ? reason.message : "Lỗi tải ảnh không xác định.";
          message.warning(retryData
            ? `Đã tạo tài khoản, ảnh đã tải lên nhưng chưa đồng bộ đủ site: ${detail}. Có thể thử đồng bộ lại bên dưới.`
            : `Đã tạo tài khoản nhưng ảnh chưa tải lên: ${detail}. Giáo viên có thể tải ảnh sau trong hồ sơ.`);
        }
      } else {
        message.success("Đã tạo hồ sơ và tài khoản giáo viên. Chọn “Gửi thông tin cấp” khi muốn gửi email.");
      }
      resetCreateForm();
      setOpen(false);
      void load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không tạo được giáo viên.");
    } finally {
      setSubmitting(false);
    }
  };

  const sendCredentials = async (row: Teacher) => {
    if (!row.slug || !row.site_code || !["ready", "failed"].includes(row.credential_email_status)) return;
    setSendingCredentials(row.slug);
    try {
      await adminApi.sendTeacherCredentials(row.slug, row.site_code);
      message.success(`Đã gửi thông tin tài khoản đến ${row.email}. Không thể gửi lại sau khi đã gửi.`);
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không gửi được email thông tin tài khoản.");
    } finally {
      setSendingCredentials("");
      void load();
    }
  };

  const columns: ColumnsType<Teacher> = [
    { title: "Ảnh", dataIndex: "avatar_secure_url", width: 72, render: (url: string | null) => <Avatar src={url || undefined} icon={<UserOutlined />} /> },
    { title: "Họ tên", dataIndex: "full_name", render: (value: string, row) => <Button type="link" disabled={!row.slug} onClick={async () => { try { setDetail(await adminApi.teacher(row.slug!, row.site_code)); } catch (reason) { message.error(reason instanceof Error ? reason.message : "Không tải được hồ sơ giáo viên."); } }}>{value}</Button> },
    { title: "Email", dataIndex: "email" },
    { title: "Điện thoại", dataIndex: "phone" },
    { title: "Trạng thái tài khoản", dataIndex: "account_status", render: (value: string | null) => <Tag color={value === "active" ? "green" : "default"}>{value || "Chưa cấp"}</Tag> },
    { title: "Trạng thái hồ sơ", dataIndex: "status" },
    { title: "Email tài khoản", render: (_: unknown, row) => {
      const canSend = ["ready", "failed"].includes(row.credential_email_status);
      const label = {
        ready: "Chưa gửi",
        processing: "Đang gửi",
        sent: "Đã gửi · khóa gửi lại",
        failed: "Gửi thất bại",
        unknown: "Chưa rõ kết quả · đã khóa gửi lại",
        changed: "Mật khẩu cấp đã thay đổi",
      }[row.credential_email_status];
      return canSend ? <Popconfirm
        title="Gửi tên đăng nhập và mật khẩu cấp đến email giáo viên?"
        description="Chỉ gửi một lần sau khi email được chấp nhận."
        okText="Gửi email"
        cancelText="Hủy"
        onConfirm={() => void sendCredentials(row)}
      ><Button size="small" loading={sendingCredentials === row.slug} disabled={Boolean(sendingCredentials)}>Gửi thông tin cấp</Button></Popconfirm>
        : <Tag color={row.credential_email_status === "sent" ? "green" : "default"}>{label || "Chưa rõ trạng thái"}</Tag>;
    } },
    { title: "Thao tác", render: (_: unknown, row) => <Space>
      <Button size="small" disabled={!row.slug || !row.account_status} onClick={async () => { const nextStatus = row.account_status === "active" ? "inactive" : "active"; try { await adminApi.setTeacherStatus(row.slug!, row.site_code, nextStatus); message.success(nextStatus === "active" ? "Đã kích hoạt tài khoản giáo viên." : "Đã ngưng tài khoản giáo viên."); void load(); } catch (reason) { message.error(reason instanceof Error ? reason.message : "Không đổi được trạng thái."); } }}>{row.account_status === "active" ? "Ngưng" : "Kích hoạt"}</Button>
      <Button danger size="small" disabled={!row.slug} onClick={() => modal.confirm({ title: "Vô hiệu hóa tài khoản và xử lý hồ sơ giáo viên?", okText: "Xóa", cancelText: "Hủy", okButtonProps: { danger: true }, onOk: async () => { if (!row.slug) return; try { await adminApi.deleteTeacher(row.slug, row.site_code); message.success("Đã xử lý yêu cầu xóa theo API."); void load(); } catch (reason) { message.error(reason instanceof Error ? reason.message : "Không xóa được."); } } })}>Xóa</Button>
    </Space> },
  ];

  const canCreate = user?.role === "admin_big" ? siteCodes.length > 0 : Boolean(site);

  return <Card title="Quản lý giáo viên" extra={<Button type="primary" disabled={!canCreate} onClick={openCreateForm}>Tạo giáo viên</Button>}>
    {user?.role === "admin_big" && <Select value={site || undefined} onChange={setSelectedSite} options={siteCodes.map((value) => ({ value, label: value }))} style={{ width: 150, marginBottom: 16 }} />}
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    {pendingAvatarSync && <Alert
      type="warning"
      showIcon
      title={`Ảnh của ${pendingAvatarSync.fullName} chưa đồng bộ đủ các cơ sở.`}
      description="Tiếp tục bằng cùng yêu cầu tải ảnh để hoàn tất các bản sao còn thiếu."
      action={<Button loading={retryingAvatarSync} onClick={() => void retryAvatarSync()}>Thử đồng bộ lại</Button>}
      style={{ marginBottom: 16 }}
    />}
    <Table rowKey="teacher_id" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 850 }} />
    <Modal title="Chi tiết hồ sơ giáo viên" open={Boolean(detail)} onCancel={() => setDetail(null)} footer={null}><pre style={{ whiteSpace: "pre-wrap", overflow: "auto" }}>{detail ? JSON.stringify(detail, null, 2) : ""}</pre></Modal>
    <Modal title="Tạo giáo viên" open={open} onCancel={() => { setOpen(false); resetCreateForm(); }} footer={null} destroyOnHidden>
      <Form form={form} layout="vertical" onFinish={create} disabled={submitting} onValuesChange={(changed, values) => {
        if (changed.full_name !== undefined && !slugEdited.current) form.setFieldValue("slug", teacherSlug(values.full_name || ""));
      }}>
        <Space orientation="vertical" size={6} style={{ marginBottom: 16 }}>
          <Typography.Text>Ảnh đại diện (không bắt buộc)</Typography.Text>
          <Space align="center">
            <Avatar size={56} src={avatarPreview || undefined} icon={<UserOutlined />} alt="Ảnh đại diện giáo viên" />
            <input ref={avatarInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => chooseAvatar(event.target.files?.[0])} />
            <Button icon={<UploadOutlined />} onClick={() => avatarInput.current?.click()}>Chọn ảnh</Button>
          </Space>
          <Typography.Text type="secondary">JPG, PNG hoặc WebP · tối đa 5 MB · lưu trên Cloudinary</Typography.Text>
        </Space>
        <Form.Item name="full_name" label="Họ tên" rules={[{ required: true, max: 150 }]}><Input maxLength={150} /></Form.Item>
        {user?.role === "admin_big" ? <Form.Item name="site_code" label="Cơ sở" rules={[{ required: true, message: "Vui lòng chọn cơ sở." }]}>
          <Select options={siteCodes.map((value) => ({ value, label: value }))} placeholder="Chọn cơ sở làm việc" />
        </Form.Item> : <Form.Item label="Cơ sở"><Input value={site || "Chưa được gán cơ sở"} disabled /></Form.Item>}
        <Form.Item label="Chuyên môn"><Input value="Tiếng Anh" disabled /></Form.Item>
        <Form.Item name="email" label="Email" rules={[{ required: true, type: "email" }]}><Input maxLength={254} /></Form.Item>
        <Form.Item name="username" label="Tên đăng nhập"><Input maxLength={100} /></Form.Item>
        <Form.Item name="slug" label="Slug hồ sơ" extra="Tự tạo từ họ tên; có thể chỉnh sửa."><Input maxLength={120} onChange={() => { slugEdited.current = true; }} /></Form.Item>
        <Form.Item name="phone" label="Điện thoại"><Input maxLength={20} /></Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting}>Tạo tài khoản</Button>
      </Form>
    </Modal>
  </Card>;
}
