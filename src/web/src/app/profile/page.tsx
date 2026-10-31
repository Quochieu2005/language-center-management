"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Space, Typography, message } from "antd";
import { RequireSession, useSession } from "@/lib/auth/session";
import { authApi, type SessionUser } from "@/lib/api/auth";
import { adminApi } from "@/lib/api/admin";
import { academicsApi } from "@/lib/api/academics";

export default function ProfileRoute() { return <RequireSession><ProfilePage /></RequireSession>; }

function ProfilePage() {
  const { user, refreshProfile } = useSession();
  const [profile, setProfile] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form] = Form.useForm();
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true); setError("");
      try {
        let result: Record<string, unknown>;
        if (user.role === "admin_big") result = await adminApi.adminBigProfile(user.slug);
        else if (user.role === "admin_small") result = await adminApi.adminSmallProfile(user.slug);
        else if (user.role === "giao_vien") result = await adminApi.teacherProfile(user.slug) as unknown as Record<string, unknown>;
        else if (user.role === "hoc_vien") result = await academicsApi.studentProfile(user.slug);
        else result = await authApi.profile(user.slug) as unknown as Record<string, unknown>;
        if (cancelled) return;
        setProfile(result);
        form.setFieldsValue(result);
      } catch (reason) { if (!cancelled) setError(reason instanceof Error ? reason.message : "Không tải được hồ sơ."); }
      finally { if (!cancelled) setLoading(false); }
    };
    void load();
    return () => { cancelled = true; };
  }, [form, user]);
  const save = async (values: Record<string, string>) => {
    if (!user) return;
    try {
      let result: Record<string, unknown>;
      if (user.role === "admin_big") result = await adminApi.updateAdminBigProfile(user.slug, { current_password: values.current_password, username: values.username, email: values.email, slug: values.slug });
      else if (user.role === "admin_small") result = await adminApi.updateAdminSmallProfile(user.slug, { full_name: values.full_name, phone: values.phone || null });
      else if (user.role === "giao_vien") result = await adminApi.updateTeacherProfile(user.slug, { full_name: values.full_name, phone: values.phone || null, specialty: values.specialty });
      else if (user.role === "hoc_vien") result = await academicsApi.updateStudentProfile(user.slug, { phone: values.phone || null, address: values.address || null });
      else { message.info("Vai trò này chỉ có API xem hồ sơ và đổi mật khẩu."); return; }
      setProfile(result); await refreshProfile(); message.success("Đã cập nhật hồ sơ.");
    } catch (reason) { message.error(reason instanceof Error ? reason.message : "Không cập nhật được hồ sơ."); }
  };
  return <main style={{ maxWidth: 880, margin: "32px auto", padding: 16 }}><Space direction="vertical" size="middle" style={{ width: "100%" }}><Card title="Hồ sơ tài khoản" extra={<Typography.Text>{roleName(user?.role)}</Typography.Text>}>
    <Typography.Paragraph type="secondary">Slug tài khoản: {user?.slug} · Cơ sở: {user?.site_code || "Toàn hệ thống"}</Typography.Paragraph>
    {error && <Alert type="error" title={error} style={{ marginBottom: 16 }} />}
    <Form form={form} layout="vertical" onFinish={save} disabled={loading}>
      {user?.role === "admin_big" ? <><Form.Item name="username" label="Tên đăng nhập"><Input maxLength={100} /></Form.Item><Form.Item name="email" label="Email"><Input type="email" maxLength={254} /></Form.Item><Form.Item name="slug" label="Slug"><Input maxLength={160} /></Form.Item><Form.Item name="current_password" label="Xác nhận mật khẩu hiện tại" rules={[{ required: true }]}><Input.Password autoComplete="current-password" /></Form.Item></>
        : user?.role === "admin_small" ? <><Form.Item name="full_name" label="Họ tên"><Input maxLength={120} /></Form.Item><Form.Item name="phone" label="Điện thoại"><Input maxLength={20} /></Form.Item></>
        : user?.role === "giao_vien" ? <><Form.Item name="full_name" label="Họ tên"><Input maxLength={150} /></Form.Item><Form.Item name="phone" label="Điện thoại"><Input maxLength={20} /></Form.Item><Form.Item name="specialty" label="Chuyên môn"><Input maxLength={200} /></Form.Item></>
        : user?.role === "hoc_vien" ? <><Form.Item name="phone" label="Điện thoại"><Input maxLength={20} /></Form.Item><Form.Item name="address" label="Địa chỉ"><Input maxLength={300} /></Form.Item></>
        : <Alert type="info" title="Vai trò này chưa có API sửa hồ sơ. Bạn vẫn có thể đổi mật khẩu." />}
      {(["admin_big", "admin_small", "giao_vien", "hoc_vien"] as SessionUser["role"][]).includes(user?.role || "admin_big") && <Button type="primary" htmlType="submit" loading={loading}>Lưu thay đổi</Button>}
    </Form>
    <Typography.Title level={5} style={{ marginTop: 24 }}>Dữ liệu hồ sơ từ API</Typography.Title><pre style={{ whiteSpace: "pre-wrap", overflow: "auto", maxHeight: 360 }}>{JSON.stringify(profile, null, 2)}</pre>
    </Card><Button href="/password/change">Đổi mật khẩu</Button></Space></main>;
}

function roleName(role?: string) { return ({ admin_big: "Admin Big", admin_small: "Admin Small", le_tan: "Lễ tân", tu_van: "Tư vấn", ke_toan: "Kế toán", xep_lop: "Nhân viên xếp lớp", giao_vien: "Giáo viên", hoc_vien: "Học viên" } as Record<string, string>)[role || ""] || "Tài khoản"; }
