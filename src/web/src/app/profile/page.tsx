"use client";

import { useEffect, useRef, useState } from "react";
import { UploadOutlined, UserOutlined } from "@ant-design/icons";
import { Alert, Avatar, Button, Card, Descriptions, Form, Input, Space, Typography, message } from "antd";
import { RequireSession, useSession } from "@/lib/auth/session";
import { authApi, type SessionUser } from "@/lib/api/auth";
import { adminApi } from "@/lib/api/admin";
import { academicsApi } from "@/lib/api/academics";
import { ApiError } from "@/lib/api/client";
import AdminLayout from "@/components/admin/layout/AdminLayout";

type ProfileRecord = Record<string, unknown>;
type ProfileField = { key: string; label: string };
type PendingAvatar = { intent_token: string; public_id: string };

const PROFILE_FIELDS: Record<string, ProfileField[]> = {
  account: [
    { key: "account_id", label: "Mã tài khoản" },
    { key: "username", label: "Tên đăng nhập" },
    { key: "email", label: "Email" },
    { key: "role", label: "Vai trò" },
    { key: "site_code", label: "Cơ sở" },
    { key: "slug", label: "Slug hồ sơ" },
    { key: "must_change_password", label: "Đổi mật khẩu lần đăng nhập tới" },
  ],
  admin_big: [
    { key: "account_id", label: "Mã tài khoản" },
    { key: "role", label: "Vai trò" },
    { key: "username", label: "Tên đăng nhập" },
    { key: "email", label: "Email" },
    { key: "slug", label: "Slug hồ sơ" },
    { key: "site_code", label: "Phạm vi cơ sở" },
    { key: "account_status", label: "Trạng thái tài khoản" },
    { key: "must_change_password", label: "Đổi mật khẩu lần đăng nhập tới" },
  ],
  admin_small: [
    { key: "profile_id", label: "Mã hồ sơ Admin" },
    { key: "account_id", label: "Mã tài khoản" },
    { key: "role", label: "Vai trò" },
    { key: "full_name", label: "Họ và tên" },
    { key: "phone", label: "Số điện thoại" },
    { key: "username", label: "Tên đăng nhập" },
    { key: "email", label: "Email" },
    { key: "slug", label: "Slug hồ sơ" },
    { key: "site_code", label: "Cơ sở phụ trách" },
    { key: "profile_status", label: "Trạng thái hồ sơ" },
    { key: "account_status", label: "Trạng thái tài khoản" },
    { key: "must_change_password", label: "Đổi mật khẩu lần đăng nhập tới" },
  ],
  giao_vien: [
    { key: "teacher_id", label: "Mã giáo viên" },
    { key: "account_id", label: "Mã tài khoản" },
    { key: "full_name", label: "Họ và tên" },
    { key: "phone", label: "Số điện thoại" },
    { key: "email", label: "Email" },
    { key: "username", label: "Tên đăng nhập" },
    { key: "slug", label: "Slug hồ sơ" },
    { key: "specialty", label: "Chuyên môn" },
    { key: "site_code", label: "Cơ sở" },
    { key: "status", label: "Trạng thái giảng dạy" },
    { key: "account_status", label: "Trạng thái tài khoản" },
  ],
  hoc_vien: [
    { key: "student_id", label: "Mã học viên" },
    { key: "full_name", label: "Họ và tên" },
    { key: "birth_date", label: "Ngày sinh" },
    { key: "gender", label: "Giới tính" },
    { key: "phone", label: "Số điện thoại" },
    { key: "email", label: "Email" },
    { key: "address", label: "Địa chỉ" },
    { key: "site_code", label: "Cơ sở hiện tại" },
    { key: "enrolled_on", label: "Ngày nhập học" },
    { key: "status", label: "Trạng thái học viên" },
    { key: "slug", label: "Slug hồ sơ" },
  ],
};

export default function ProfileRoute() {
  return <RequireSession><ProfileRouteContent /></RequireSession>;
}

function ProfileRouteContent() {
  const { user } = useSession();
  const hasAdminShell = ["admin_big", "admin_small", "le_tan", "tu_van", "ke_toan", "xep_lop"].includes(user?.role || "");
  const content = <ProfilePage />;

  return hasAdminShell ? <AdminLayout>{content}</AdminLayout> : <main>{content}</main>;
}

function ProfilePage() {
  const { user, refreshProfile } = useSession();
  const [profile, setProfile] = useState<ProfileRecord>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [avatarError, setAvatarError] = useState("");
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [pendingAvatar, setPendingAvatar] = useState<PendingAvatar | null>(null);
  const avatarInput = useRef<HTMLInputElement>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        let result: ProfileRecord;
        if (user.role === "admin_big") result = await adminApi.adminBigProfile(user.slug);
        else if (user.role === "admin_small") result = await adminApi.adminSmallProfile(user.slug);
        else if (user.role === "giao_vien") result = await adminApi.teacherProfile(user.slug);
        else if (user.role === "hoc_vien") result = await academicsApi.studentProfile(user.slug);
        else result = (await authApi.profile(user.slug)).user as unknown as ProfileRecord;
        if (cancelled) return;
        setProfile(result);
        form.setFieldsValue(result);
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Không tải được hồ sơ.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [form, user]);

  const save = async (values: Record<string, string>) => {
    if (!user) return;
    try {
      let result: ProfileRecord;
      if (user.role === "admin_big") {
        result = await adminApi.updateAdminBigProfile(user.slug, {
          current_password: values.current_password,
          username: values.username,
          email: values.email,
          slug: values.slug,
        });
      } else if (user.role === "admin_small") {
        result = await adminApi.updateAdminSmallProfile(user.slug, { full_name: values.full_name, phone: values.phone || null });
      } else if (user.role === "giao_vien") {
        result = await adminApi.updateTeacherProfile(user.slug, { full_name: values.full_name, phone: values.phone || null, specialty: values.specialty });
      } else if (user.role === "hoc_vien") {
        result = await academicsApi.updateStudentProfile(user.slug, { phone: values.phone || null, address: values.address || null });
      } else {
        message.info("Vai trò này chỉ có API xem hồ sơ và đổi mật khẩu.");
        return;
      }
      setProfile(result);
      await refreshProfile();
      message.success("Đã cập nhật hồ sơ.");
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không cập nhật được hồ sơ.");
    }
  };

  const fields = (user && PROFILE_FIELDS[user.role]) || PROFILE_FIELDS.account;
  const canUploadAvatar = user?.role === "admin_big" || user?.role === "admin_small";
  const avatarUrl = typeof profile.avatar_secure_url === "string" ? profile.avatar_secure_url : undefined;
  const profileItems = fields.map(({ key, label }) => ({
    key,
    label,
    children: formatProfileValue(key, profile[key]),
  }));

  const completeAvatar = async (intentToken: string, publicId: string) => {
    if (!user) return;
    setAvatarLoading(true);
    setAvatarError("");
    try {
      const result = await adminApi.completeAdminAvatarUpload(user.slug, {
        intent_token: intentToken,
        public_id: publicId,
      });
      setProfile((current) => ({ ...current, avatar_secure_url: result.avatar_secure_url }));
      setPendingAvatar(null);
      message.success("Đã cập nhật ảnh đại diện.");
    } catch (reason) {
      const detail = reason instanceof Error ? reason.message : "Chưa đồng bộ được ảnh qua các cơ sở.";
      setAvatarError(`${detail} Bạn có thể bấm tiếp tục đồng bộ ảnh để thử lại.`);
      if (reason instanceof ApiError && [400, 401, 403, 404, 409].includes(reason.status)) {
        setPendingAvatar(null);
      } else {
        setPendingAvatar({ intent_token: intentToken, public_id: publicId });
      }
    } finally {
      setAvatarLoading(false);
    }
  };

  const chooseAvatar = async (file?: File) => {
    if (!file || !user || !canUploadAvatar) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setAvatarError("Chỉ nhận ảnh JPG, PNG hoặc WebP.");
      return;
    }
    if (file.size < 1 || file.size > 5 * 1024 * 1024) {
      setAvatarError("Ảnh phải có dung lượng tối đa 5 MB.");
      return;
    }
    setAvatarLoading(true);
    setAvatarError("");
    try {
      const intent = await adminApi.createAdminAvatarUploadIntent(user.slug);
      const body = new FormData();
      body.append("file", file);
      body.append("api_key", intent.api_key);
      Object.entries(intent.fields).forEach(([key, value]) => body.append(key, value));
      const response = await fetch(intent.upload_url, { method: "POST", body, cache: "no-store" });
      const uploaded = await response.json().catch(() => null) as { public_id?: unknown } | null;
      if (!response.ok || typeof uploaded?.public_id !== "string") {
        throw new Error("Cloudinary không nhận được ảnh. Hãy kiểm tra cấu hình và thử lại.");
      }
      const pending = { intent_token: intent.intent_token, public_id: uploaded.public_id };
      setPendingAvatar(pending);
      await completeAvatar(pending.intent_token, pending.public_id);
    } catch (reason) {
      const detail = reason instanceof Error ? reason.message : "Không tải được ảnh đại diện.";
      setAvatarError(detail);
      message.error(detail);
    } finally {
      setAvatarLoading(false);
      if (avatarInput.current) avatarInput.current.value = "";
    }
  };

  return (
    <div style={{ maxWidth: 1040, margin: "32px auto", padding: 16 }}>
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
        <Card title="Hồ sơ tài khoản" extra={<Typography.Text>{roleName(user?.role)}</Typography.Text>}>
          {canUploadAvatar && <Space align="center" size="middle" style={{ marginBottom: 20 }}>
            <Avatar size={80} src={avatarUrl} icon={<UserOutlined />} alt="Ảnh đại diện" />
            <Space orientation="vertical" size={4}>
              <Typography.Text strong>Ảnh đại diện</Typography.Text>
              <Typography.Text type="secondary">JPG, PNG hoặc WebP · tối đa 5 MB</Typography.Text>
              <Space>
                <input
                  ref={avatarInput}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  hidden
                  onChange={(event) => void chooseAvatar(event.target.files?.[0])}
                />
                <Button
                  icon={<UploadOutlined />}
                  loading={avatarLoading}
                  disabled={Boolean(pendingAvatar)}
                  onClick={() => avatarInput.current?.click()}
                >Tải ảnh lên</Button>
                {pendingAvatar && <Button loading={avatarLoading} onClick={() => void completeAvatar(pendingAvatar.intent_token, pendingAvatar.public_id)}>
                  Tiếp tục đồng bộ ảnh
                </Button>}
              </Space>
            </Space>
          </Space>}
          {avatarError && <Alert type="error" title={avatarError} style={{ marginBottom: 16 }} />}
          <Typography.Paragraph type="secondary">
            Thông tin được tải từ hồ sơ của bạn tại cơ sở có quyền truy cập. Mật khẩu và mã bảo mật không được hiển thị.
          </Typography.Paragraph>
          {error && <Alert type="error" title={error} style={{ marginBottom: 16 }} />}
          <Descriptions
            title="Thông tin trong hệ thống"
            bordered
            size="small"
            column={{ xs: 1, sm: 2, md: 2 }}
            items={profileItems}
          />
          <Typography.Title level={5} style={{ marginTop: 28 }}>Thông tin có thể chỉnh sửa</Typography.Title>
          <Form form={form} layout="vertical" onFinish={save} disabled={loading}>
            {user?.role === "admin_big" ? <>
              <Form.Item name="username" label="Tên đăng nhập"><Input maxLength={100} /></Form.Item>
              <Form.Item name="email" label="Email"><Input type="email" maxLength={254} /></Form.Item>
              <Form.Item name="slug" label="Slug"><Input maxLength={160} /></Form.Item>
              <Form.Item name="current_password" label="Xác nhận mật khẩu hiện tại" rules={[{ required: true }]}>
                <Input.Password autoComplete="current-password" />
              </Form.Item>
            </> : user?.role === "admin_small" ? <>
              <Form.Item name="full_name" label="Họ tên"><Input maxLength={120} /></Form.Item>
              <Form.Item name="phone" label="Điện thoại"><Input maxLength={20} /></Form.Item>
            </> : user?.role === "giao_vien" ? <>
              <Form.Item name="full_name" label="Họ tên"><Input maxLength={150} /></Form.Item>
              <Form.Item name="phone" label="Điện thoại"><Input maxLength={20} /></Form.Item>
              <Form.Item name="specialty" label="Chuyên môn"><Input maxLength={200} /></Form.Item>
            </> : user?.role === "hoc_vien" ? <>
              <Form.Item name="phone" label="Điện thoại"><Input maxLength={20} /></Form.Item>
              <Form.Item name="address" label="Địa chỉ"><Input maxLength={300} /></Form.Item>
            </> : <Alert type="info" title="Vai trò này chưa có API sửa hồ sơ. Bạn vẫn có thể đổi mật khẩu." />}
            {(["admin_big", "admin_small", "giao_vien", "hoc_vien"] as SessionUser["role"][]).includes(user?.role || "admin_big") && (
              <Button type="primary" htmlType="submit" loading={loading}>Lưu thay đổi</Button>
            )}
          </Form>
        </Card>
        <Button href="/password/change">Đổi mật khẩu</Button>
      </Space>
    </div>
  );
}

function formatProfileValue(key: string, value: unknown): string {
  if (key === "site_code" && value == null) return "Toàn hệ thống";
  if (value == null || value === "") return "Chưa cập nhật";
  if (typeof value === "boolean") {
    if (key === "must_change_password") return value ? "Bắt buộc đổi ở lần đăng nhập tới" : "Không bắt buộc";
    return value ? "Có" : "Không";
  }
  const text = String(value);
  const labels: Record<string, string> = {
    active: "Đang hoạt động", inactive: "Đã vô hiệu hóa", dang_lam: "Đang làm việc",
    nghi_viec: "Đã nghỉ việc", dang_day: "Đang giảng dạy", tam_nghi: "Tạm nghỉ",
    dang_hoc: "Đang học", bao_luu: "Bảo lưu", da_chuyen_di: "Đã chuyển cơ sở",
    nam: "Nam", nu: "Nữ", khac: "Khác",
  };
  return key === "role" ? roleName(text) : labels[text] || text;
}

function roleName(role?: string) {
  return ({
    admin_big: "Admin Big", admin_small: "Admin Small", le_tan: "Lễ tân",
    tu_van: "Tư vấn", ke_toan: "Kế toán", xep_lop: "Nhân viên xếp lớp",
    giao_vien: "Giáo viên", hoc_vien: "Học viên",
  } as Record<string, string>)[role || ""] || "Tài khoản";
}
