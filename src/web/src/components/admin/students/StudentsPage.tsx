"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, App, Avatar, Button, Card, Col, Descriptions, Form, Input, Modal, Row, Select, Space, Table, Tag, Tooltip, Typography } from "antd";
import { SearchOutlined, UploadOutlined, UserOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { adminApi, type Student, type StudentProfile, type StudentProfileWrite } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/client";
import { ALL_SITES, useSiteScope } from "@/lib/auth/site-scope";

type PendingStudentAvatarSync = {
  slug: string;
  siteCode: string;
  intentToken: string;
  publicId: string;
  fullName: string;
};

const studentSlug = (value: string) => value.toLowerCase().replace(/đ/g, "d").normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const studentGender = (value: string | null) => {
  const normalized = value?.trim().toLocaleLowerCase("vi-VN");
  return normalized === "nam" ? "Nam" : normalized === "nữ" ? "Nữ" : normalized === "khác" ? "Khác" : undefined;
};

export default function StudentsPage({ initialSearch }: { initialSearch: string }) {
  const { message, modal } = App.useApp();
  const { user } = useSession();
  const { siteCodes, selectedSite, setSelectedSite, loadingSites } = useSiteScope();
  const [rows, setRows] = useState<Student[]>([]);
  const [searchDraft, setSearchDraft] = useState(initialSearch);
  const [search, setSearch] = useState(initialSearch);
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [partial, setPartial] = useState<string[]>([]);
  const [editor, setEditor] = useState<"create" | "edit" | null>(null);
  const [editingStudent, setEditingStudent] = useState<Student | null>(null);
  const [saving, setSaving] = useState(false);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState("");
  const [pendingAvatarSync, setPendingAvatarSync] = useState<PendingStudentAvatarSync | null>(null);
  const [retryingAvatarSync, setRetryingAvatarSync] = useState(false);
  const [viewingStudent, setViewingStudent] = useState<StudentProfile | null>(null);
  const [loadingDetail, setLoadingDetail] = useState("");
  const [issuingSlug, setIssuingSlug] = useState("");
  const avatarInput = useRef<HTMLInputElement>(null);
  const slugEdited = useRef(false);
  const [form] = Form.useForm<StudentProfileWrite>();
  const isAdminBig = user?.role === "admin_big";
  const canManage = isAdminBig || user?.role === "admin_small" || user?.role === "tu_van";
  const canIssueAccount = isAdminBig || user?.role === "admin_small";
  const site = isAdminBig ? selectedSite || undefined : user?.site_code || undefined;
  const requestedSite = site === ALL_SITES ? undefined : site;

  useEffect(() => {
    if (!avatarPreview.startsWith("blob:")) return;
    return () => URL.revokeObjectURL(avatarPreview);
  }, [avatarPreview]);

  const load = useCallback(async (searchValue = search, statusValue = status) => {
    if (!site) {
      setRows([]); setPartial([]);
      if (loadingSites) { setLoading(true); setError(""); }
      else { setLoading(false); setError("Chưa xác định được cơ sở cần tải học viên."); }
      return;
    }
    setLoading(true);
    try {
      const result = await adminApi.students({
        site_code: isAdminBig ? requestedSite : undefined,
        search: searchValue.trim() || undefined,
        status: statusValue === "all" ? undefined : statusValue,
        limit: 100,
      });
      setRows(result.results); setPartial(result.missing_sites || []); setError("");
    } catch (reason) {
      setRows([]); setError(reason instanceof Error ? reason.message : "Không tải được học viên.");
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) {
        const payload = reason.payload as unknown as { results: Student[]; missing_sites?: string[] };
        setRows(payload.results); setPartial(payload.missing_sites || []);
      }
    } finally { setLoading(false); }
  }, [isAdminBig, loadingSites, requestedSite, search, site, status]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const closeEditor = () => {
    setEditor(null); setEditingStudent(null); form.resetFields();
    slugEdited.current = false;
    setAvatarFile(null); setAvatarPreview("");
    if (avatarInput.current) avatarInput.current.value = "";
  };

  const openCreate = () => {
    if (!site || site === ALL_SITES) return;
    slugEdited.current = false;
    form.resetFields(); setEditingStudent(null); setAvatarFile(null); setAvatarPreview("");
    form.setFieldsValue({ slug: "" });
    if (avatarInput.current) avatarInput.current.value = "";
    setEditor("create");
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
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(file));
  };

  const uploadAvatar = async (slug: string, targetSite: string, fullName: string, file: File) => {
    const siteCode = isAdminBig ? targetSite : undefined;
    const intent = await adminApi.createStudentAvatarUploadIntent(slug, siteCode);
    const body = new FormData();
    body.append("file", file);
    body.append("api_key", intent.api_key);
    Object.entries(intent.fields).forEach(([key, value]) => body.append(key, value));
    const upload = await fetch(intent.upload_url, { method: "POST", body, cache: "no-store" });
    const uploaded = await upload.json().catch(() => null) as { public_id?: unknown } | null;
    if (!upload.ok || typeof uploaded?.public_id !== "string") {
      throw new Error("Cloudinary chưa nhận được ảnh.");
    }
    const pending = {
      slug,
      siteCode: targetSite,
      intentToken: intent.intent_token,
      publicId: uploaded.public_id,
      fullName,
    };
    setPendingAvatarSync(pending);
    const result = await adminApi.completeStudentAvatarUpload(
      slug,
      { intent_token: pending.intentToken, public_id: pending.publicId },
      siteCode,
    );
    if (!result.complete) throw new Error("API chưa xác nhận lưu ảnh vào hồ sơ.");
    setPendingAvatarSync(null);
  };

  const retryAvatarSync = async () => {
    if (!pendingAvatarSync) return;
    setRetryingAvatarSync(true);
    try {
      const result = await adminApi.completeStudentAvatarUpload(
        pendingAvatarSync.slug,
        { intent_token: pendingAvatarSync.intentToken, public_id: pendingAvatarSync.publicId },
        isAdminBig ? pendingAvatarSync.siteCode : undefined,
      );
      if (!result.complete) throw new Error("API chưa xác nhận lưu ảnh vào hồ sơ.");
      setPendingAvatarSync(null);
      message.success(`Đã lưu ảnh đại diện cho ${pendingAvatarSync.fullName}.`);
      void load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Chưa lưu được ảnh; hãy thử lại.");
    } finally {
      setRetryingAvatarSync(false);
    }
  };

  const openEdit = async (row: Student) => {
    setLoadingDetail(row.slug);
    try {
      const profile = await adminApi.student(row.slug, isAdminBig ? row.site_code : undefined);
      form.setFieldsValue({
        full_name: profile.full_name,
        slug: profile.slug,
        birth_date: profile.birth_date || undefined,
        gender: studentGender(profile.gender),
        phone: profile.phone || undefined,
        email: profile.email || undefined,
        address: profile.address || undefined,
      });
      slugEdited.current = true;
      setAvatarFile(null);
      setAvatarPreview(profile.avatar_secure_url || "");
      if (avatarInput.current) avatarInput.current.value = "";
      setEditingStudent(row); setEditor("edit");
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không tải được hồ sơ học viên.");
    } finally { setLoadingDetail(""); }
  };

  const openView = async (row: Student) => {
    setLoadingDetail(row.slug);
    try {
      setViewingStudent(await adminApi.student(row.slug, isAdminBig ? row.site_code : undefined));
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không tải được hồ sơ học viên.");
    } finally { setLoadingDetail(""); }
  };

  const submit = async (values: StudentProfileWrite) => {
    if (!site || (editor === "create" && site === ALL_SITES)) return;
    setSaving(true);
    try {
      if (editor === "create") {
        const created = await adminApi.createStudent(values, isAdminBig ? site : undefined);
        if (avatarFile) {
          try {
            await uploadAvatar(created.slug, created.site_code, values.full_name, avatarFile);
            message.success(`Đã tạo hồ sơ (slug: ${created.slug}) và lưu ảnh đại diện. Tài khoản chưa được cấp.`);
          } catch (reason) {
            message.warning(`Đã tạo hồ sơ (slug: ${created.slug}) nhưng ảnh chưa được xác nhận: ${reason instanceof Error ? reason.message : "hãy thử lại trong phần Sửa hồ sơ."}`);
          }
        } else {
          message.success(`Đã tạo hồ sơ (slug: ${created.slug}). Tài khoản và mật khẩu chưa được cấp.`);
        }
        const filtersChanged = search !== "" || status !== "all";
        setSearch(""); setSearchDraft(""); setStatus("all");
        closeEditor();
        if (!filtersChanged) void load("", "all");
      } else if (editingStudent) {
        await adminApi.updateStudent(editingStudent.slug, {
          full_name: values.full_name,
          birth_date: values.birth_date,
          gender: values.gender,
          phone: values.phone,
          email: values.email,
          address: values.address,
        }, isAdminBig ? editingStudent.site_code : undefined);
        if (avatarFile) {
          try {
            await uploadAvatar(editingStudent.slug, editingStudent.site_code, values.full_name, avatarFile);
            message.success("Đã cập nhật hồ sơ và ảnh đại diện.");
          } catch (reason) {
            message.warning(`Đã cập nhật hồ sơ nhưng ảnh chưa được xác nhận: ${reason instanceof Error ? reason.message : "hãy thử lại trong phần Sửa hồ sơ."}`);
          }
        } else {
          message.success("Đã cập nhật hồ sơ học viên.");
        }
        closeEditor(); void load();
      }
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không lưu được hồ sơ học viên.");
    } finally { setSaving(false); }
  };

  const issueAccount = async (row: Student) => {
    setIssuingSlug(row.slug);
    try {
      const result = await adminApi.issueStudentAccount(row.slug, isAdminBig ? row.site_code : undefined);
      message.success(result.email_sent ? "Đã cấp tài khoản và gửi mật khẩu qua email." : "Đã xử lý cấp tài khoản.");
      setRows((current) => current.map((student) => student.student_id === row.student_id
        ? { ...student, account_issued: true, account_issue_eligible: false }
        : student));
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không cấp được tài khoản.");
    } finally { setIssuingSlug(""); }
  };

  const removeStudent = (row: Student) => modal.confirm({
    title: "Xóa hồ sơ học viên này?",
    content: "Chỉ xóa được hồ sơ chưa có tài khoản, đăng ký hoặc lịch sử chuyển cơ sở. Hồ sơ có dữ liệu học tập, điểm danh hay học phí sẽ được giữ lại để bảo toàn lịch sử.",
    okText: "Xóa hồ sơ", cancelText: "Hủy", okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await adminApi.deleteStudent(row.slug, isAdminBig ? row.site_code : undefined);
        message.success("Đã xóa hồ sơ học viên."); void load();
      } catch (reason) {
        message.error(reason instanceof Error ? reason.message : "Không xóa được hồ sơ học viên.");
      }
    },
  });

  const columns: ColumnsType<Student> = [
    {
      title: "Ảnh", dataIndex: "avatar_secure_url", width: 64,
      render: (value: string | null, row: Student) => <Avatar size={40} src={value || undefined} icon={<UserOutlined />} alt={`Ảnh đại diện ${row.full_name}`} />,
    },
    { title: "Họ tên", dataIndex: "full_name" },
    { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Email", dataIndex: "email", render: (value: string | null) => value || "—" },
    { title: "Điện thoại", dataIndex: "phone", render: (value: string | null) => value || "—" },
    { title: "Tình trạng", dataIndex: "status", render: (value: string) => <Tag>{value}</Tag> },
    {
      title: "Tài khoản", dataIndex: "account_issued",
      render: (issued: boolean, row: Student) => issued
        ? <Tag color="green">Đã cấp</Tag>
        : canIssueAccount
          ? <Tooltip title={row.account_issue_eligible ? undefined : "Chỉ cấp tài khoản cho hồ sơ đang học có email hợp lệ."}><span><Button size="small" disabled={!row.account_issue_eligible} loading={issuingSlug === row.slug} onClick={() => void issueAccount(row)}>Cấp tài khoản</Button></span></Tooltip>
          : <Tag>Chưa cấp</Tag>,
    },
    ...(canManage ? [{
      title: "Thao tác",
      render: (_: unknown, row: Student) => <Space>
        <Button size="small" loading={loadingDetail === row.slug} onClick={() => void openEdit(row)}>Sửa</Button>
        <Button danger size="small" onClick={() => removeStudent(row)}>Xóa</Button>
      </Space>,
    }] : [{
      title: "Thao tác",
      render: (_: unknown, row: Student) => <Button size="small" loading={loadingDetail === row.slug} onClick={() => void openView(row)}>Xem</Button>,
    }]),
  ];

  return <>
    <Card title="Hồ sơ học viên" extra={<Space wrap>
      <Input allowClear value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} onPressEnter={() => setSearch(searchDraft)} placeholder="Tìm tên, email, mã..." prefix={<SearchOutlined />} style={{ width: 240 }} />
      <Button onClick={() => setSearch(searchDraft)}>Tìm kiếm</Button>
      {canManage && <Button type="primary" disabled={!site || site === ALL_SITES} title={site === ALL_SITES ? "Chọn một cơ sở cụ thể để tạo hồ sơ." : undefined} onClick={openCreate}>Tạo học viên</Button>}
    </Space>}>
      <Space style={{ marginBottom: 16 }} wrap>
        {isAdminBig && <Select value={site} onChange={setSelectedSite} loading={loadingSites} disabled={loadingSites} style={{ width: 180 }} options={[{ value: ALL_SITES, label: "Toàn hệ thống" }, ...siteCodes.map((value) => ({ value, label: value }))]} placeholder="Chọn phạm vi" />}
        <Select value={status} onChange={setStatus} style={{ width: 170 }} options={[
          { value: "all", label: "Mọi trạng thái" }, { value: "dang_hoc", label: "Đang học" },
          { value: "bao_luu", label: "Bảo lưu" }, { value: "da_chuyen_di", label: "Đã chuyển đi" },
          { value: "nghi_hoc", label: "Nghỉ học" },
        ]} />
        <Button onClick={() => { setSearch(""); setSearchDraft(""); setStatus("all"); }}>Đặt lại</Button>
      </Space>
      {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
      {partial.length > 0 && <Alert type="warning" showIcon title={`Global Query thiếu site: ${partial.join(", ")}; dữ liệu chưa đầy đủ.`} style={{ marginBottom: 16 }} />}
      {pendingAvatarSync && <Alert type="warning" showIcon title={`Ảnh của ${pendingAvatarSync.fullName} đã tải lên nhưng chưa lưu vào hồ sơ.`} action={<Button size="small" loading={retryingAvatarSync} onClick={() => void retryAvatarSync()}>Thử lưu lại</Button>} style={{ marginBottom: 16 }} />}
      <Table rowKey="student_id" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 1120 }} />
    </Card>
    <Modal
      title={editor === "create" ? "Tạo hồ sơ học viên" : "Sửa hồ sơ học viên"}
      open={editor !== null}
      onCancel={closeEditor}
      footer={null}
      width={860}
      forceRender
    >
      <Form form={form} layout="vertical" onFinish={submit} disabled={saving} scrollToFirstError onValuesChange={(changed, values) => {
        if (changed.slug !== undefined) slugEdited.current = true;
        if (changed.full_name !== undefined && !slugEdited.current) form.setFieldValue("slug", studentSlug(values.full_name || ""));
      }}>
        <Typography.Text type="secondary">Cơ sở: {site || "Chưa chọn"}. Tạo hồ sơ không cấp tài khoản hoặc gửi mật khẩu.</Typography.Text>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12, margin: "16px 0", padding: 12, border: "1px solid #f0f0f0", borderRadius: 8 }}>
          <Avatar size={52} src={avatarPreview || undefined} icon={<UserOutlined />} alt="Ảnh đại diện học viên" />
          <div>
            <Typography.Text strong>Ảnh đại diện </Typography.Text><Typography.Text type="secondary">(không bắt buộc)</Typography.Text>
            <Space size={8} wrap>
              <input ref={avatarInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => { chooseAvatar(event.target.files?.[0]); event.currentTarget.value = ""; }} />
              <Button size="small" icon={<UploadOutlined />} onClick={() => avatarInput.current?.click()}>Chọn ảnh</Button>
              <Typography.Text type="secondary">JPG/PNG/WebP · tối đa 5 MB</Typography.Text>
            </Space>
          </div>
        </div>
        <Row gutter={16}>
          <Col xs={24} md={12}><Form.Item name="full_name" label="Họ tên" rules={[{ required: true, whitespace: true, message: "Nhập họ tên học viên." }, { max: 150 }]}><Input maxLength={150} /></Form.Item></Col>
          <Col xs={24} md={12}><Form.Item name="email" label="Email" rules={[{ type: "email", message: "Email không hợp lệ." }]} extra={editingStudent?.account_issued ? "Email đã gắn với tài khoản nên không thể đổi." : "Cần email hợp lệ để cấp tài khoản sau này."}><Input maxLength={254} disabled={Boolean(editingStudent?.account_issued)} /></Form.Item></Col>
          <Col xs={24} md={12}><Form.Item name="slug" label="Slug hồ sơ" extra={editor === "edit" ? "Slug được giữ nguyên sau khi tạo." : "Tự tạo theo họ tên; có thể chỉnh sửa. Nếu trùng tại cơ sở, API tự thêm số."} rules={[{ max: 160, message: "Slug tối đa 160 ký tự." }]}><Input maxLength={160} disabled={editor === "edit"} /></Form.Item></Col>
          <Col xs={24} md={12}><Form.Item name="birth_date" label="Ngày sinh"><Input type="date" /></Form.Item></Col>
          <Col xs={24} md={12}><Form.Item name="gender" label="Giới tính"><Select allowClear placeholder="Chọn giới tính" options={[{ value: "Nam", label: "Nam" }, { value: "Nữ", label: "Nữ" }, { value: "Khác", label: "Khác" }]} /></Form.Item></Col>
          <Col xs={24} md={12}><Form.Item name="phone" label="Số điện thoại"><Input maxLength={20} /></Form.Item></Col>
          <Col xs={24}><Form.Item name="address" label="Địa chỉ"><Input maxLength={300} /></Form.Item></Col>
        </Row>
        <Button type="primary" htmlType="submit" block loading={saving}>{editor === "create" ? "Tạo hồ sơ" : "Lưu thay đổi"}</Button>
      </Form>
    </Modal>
    <Modal title="Thông tin học viên" open={Boolean(viewingStudent)} onCancel={() => setViewingStudent(null)} footer={null}>
      {viewingStudent && <Space orientation="vertical" size={16} style={{ width: "100%" }}>
        <Space><Avatar size={56} src={viewingStudent.avatar_secure_url || undefined} icon={<UserOutlined />} /><Typography.Text strong>{viewingStudent.full_name}</Typography.Text></Space>
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label="Mã học viên">{viewingStudent.student_id}</Descriptions.Item>
          <Descriptions.Item label="Cơ sở">{viewingStudent.site_code}</Descriptions.Item>
          <Descriptions.Item label="Email">{viewingStudent.email || "—"}</Descriptions.Item>
          <Descriptions.Item label="Điện thoại">{viewingStudent.phone || "—"}</Descriptions.Item>
          <Descriptions.Item label="Ngày sinh">{viewingStudent.birth_date || "—"}</Descriptions.Item>
          <Descriptions.Item label="Giới tính">{viewingStudent.gender || "—"}</Descriptions.Item>
          <Descriptions.Item label="Trạng thái">{viewingStudent.status}</Descriptions.Item>
          <Descriptions.Item label="Ngày tạo hồ sơ">{viewingStudent.enrolled_on}</Descriptions.Item>
          <Descriptions.Item label="Địa chỉ" span={2}>{viewingStudent.address || "—"}</Descriptions.Item>
        </Descriptions>
      </Space>}
    </Modal>
  </>;
}
