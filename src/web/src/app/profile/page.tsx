"use client";

import { useEffect, useState } from "react";
import { UserOutlined } from "@ant-design/icons";
import { Alert, Avatar, Button, Card, Descriptions, Form, Input, Space, Typography } from "antd";
import { message } from "@/lib/ui/message";
import { RequireSession, useSession } from "@/lib/auth/session";
import { authApi, type SessionUser } from "@/lib/api/auth";
import { adminApi } from "@/lib/api/admin";
import { academicsApi } from "@/lib/api/academics";
import { SelfAvatarUploader } from "@/components/shared/SelfAvatarUploader";
import AdminLayout from "@/components/admin/layout/AdminLayout";

type ProfileRecord = Record<string, unknown>;
type ProfileField = { key: string; label: string };

const PROFILE_FIELDS: Record<string, ProfileField[]> = {
  account: [
    { key: "account_id", label: "Mã tài khoản" },
    { key: "username", label: "Tên đăng nhập" },
    { key: "email", label: "Email" },
    { key: "role", label: "Vai trò" },
    { key: "site_code", label: "Cơ sở" },
    { key: "slug", label: "Slug hồ sơ" },
    { key: "must_change_password", label: "Mật khẩu được cấp" },
  ],
  admin_big: [
    { key: "account_id", label: "Mã tài khoản" },
    { key: "role", label: "Vai trò" },
    { key: "username", label: "Tên đăng nhập" },
    { key: "email", label: "Email" },
    { key: "slug", label: "Slug hồ sơ" },
    { key: "site_code", label: "Phạm vi cơ sở" },
    { key: "account_status", label: "Trạng thái tài khoản" },
    { key: "must_change_password", label: "Mật khẩu được cấp" },
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
    { key: "must_change_password", label: "Mật khẩu được cấp" },
  ],
  giao_vien: [
    { key: "teacher_id", label: "Mã giáo viên" },
    { key: "account_id", label: "Mã tài khoản" },
    { key: "full_name", label: "Họ và tên" },
    { key: "phone", label: "Số điện thoại" },
    { key: "email", label: "Email" },
    { key: "username", label: "Tên đăng nhập" },
    { key: "slug", label: "Slug hồ sơ" },
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
  const hasAdminShell = ["admin_big", "admin_small", "le_tan", "tu_van", "ke_toan"].includes(user?.role || "");
  const content = <ProfilePage />;

  return hasAdminShell ? <AdminLayout>{content}</AdminLayout> : <main>{content}</main>;
}

function ProfilePage() {
  const { user, refreshProfile } = useSession();
  const [profile, setProfile] = useState<ProfileRecord>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
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
        else if (user.role === "giao_vien") {
          const [teacher, account] = await Promise.all([
            adminApi.teacherProfile(user.slug), authApi.profile(user.slug),
          ]);
          result = { ...teacher, avatar_secure_url: account.user.avatar_secure_url };
        } else if (user.role === "hoc_vien") {
          // Students' photo lives on their profile (HocVien), the one staff see and transfers copy.
          result = await academicsApi.studentProfile(user.slug);
        }
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
        result = await adminApi.updateTeacherProfile(user.slug, { full_name: values.full_name, phone: values.phone || null });
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
  const canUploadAvatar = Boolean(user);
  const avatarUrl = typeof profile.avatar_secure_url === "string" ? profile.avatar_secure_url : undefined;
  const profileItems = fields.map(({ key, label }) => ({
    key,
    label,
    children: formatProfileValue(key, profile[key]),
  }));

  return (
    <div style={{ maxWidth: 1040, margin: "32px auto", padding: 16 }}>
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
        <Card title="Hồ sơ tài khoản" extra={<Typography.Text>{roleName(user?.role)}</Typography.Text>}>
          {canUploadAvatar && <Space align="center" size="middle" style={{ marginBottom: 20 }}>
            <Avatar size={80} src={avatarUrl} icon={<UserOutlined />} alt="Ảnh đại diện" />
            <Space orientation="vertical" size={4}>
              <Typography.Text strong>Ảnh đại diện</Typography.Text>
              <Typography.Text type="secondary">JPG, PNG hoặc WebP · tối đa 5 MB</Typography.Text>
              <SelfAvatarUploader
                slug={user?.slug}
                hasAvatar={Boolean(avatarUrl)}
                api={user?.role === "hoc_vien"
                  ? { createIntent: academicsApi.createStudentSelfAvatarIntent, complete: academicsApi.completeStudentSelfAvatar }
                  : undefined}
                onUploaded={(url) => {
                  setProfile((current) => ({ ...current, avatar_secure_url: url }));
                  void refreshProfile();
                }}
              />
            </Space>
          </Space>}
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
    if (key === "must_change_password") return value ? "Được trung tâm cấp — nên đổi để bảo mật" : "Đã đổi hoặc không yêu cầu";
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
    admin_big: "Admin Big", admin_small: "Admin Small", le_tan: "Kế toán & Lễ tân",
    tu_van: "Tư vấn & xếp lớp", ke_toan: "Kế toán & Lễ tân",
    giao_vien: "Giáo viên", hoc_vien: "Học viên",
  } as Record<string, string>)[role || ""] || "Tài khoản";
}
