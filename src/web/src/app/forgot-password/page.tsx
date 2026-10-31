"use client";

import Link from "next/link";
import { Alert, Button, Card, Form, Input, Space, Typography, message } from "antd";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

export default function ForgotPasswordPage() {
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const router = useRouter();
  const forgot = async (values: { email: string }) => {
    setBusy(true); setError(""); setEmail(values.email);
    try { const result = await authApi.forgotPassword(values.email); message.success(result.detail); setSent(true); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không gửi được yêu cầu."); }
    finally { setBusy(false); }
  };
  const reset = async (values: { otp: string; new_password: string; confirm_password: string }) => {
    setBusy(true); setError("");
    try { const result = await authApi.resetPassword(email, values.otp, values.new_password, values.confirm_password); message.success(result.detail); router.replace("/login"); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không đặt lại được mật khẩu."); }
    finally { setBusy(false); }
  };
  return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20 }}>
    <Card style={{ width: "min(100%, 480px)" }}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <div><Typography.Title level={2}>Khôi phục mật khẩu</Typography.Title><Typography.Text type="secondary">Mã OTP có hiệu lực 2 phút. API luôn trả cùng thông báo để bảo vệ email.</Typography.Text></div>
        {error && <Alert type="error" showIcon title={error} />}
        {!sent ? <Form layout="vertical" onFinish={forgot}><Form.Item name="email" label="Email tài khoản" rules={[{ required: true, type: "email" }]}><Input autoComplete="email" maxLength={254} /></Form.Item><Button type="primary" htmlType="submit" loading={busy} block>Gửi mã OTP</Button></Form>
          : <Form layout="vertical" onFinish={reset}><Alert type="info" title="Nếu email thuộc tài khoản quản trị, mã sẽ được gửi đến hộp thư." /><Form.Item name="otp" label="Mã OTP 6 chữ số" rules={[{ required: true, len: 6 }]}><Input inputMode="numeric" maxLength={6} /></Form.Item><Form.Item name="new_password" label="Mật khẩu mới" rules={[{ required: true, min: 12, max: 128 }]}><Input.Password autoComplete="new-password" /></Form.Item><Form.Item name="confirm_password" label="Nhập lại mật khẩu" dependencies={["new_password"]} rules={[{ required: true }, ({ getFieldValue }) => ({ validator(_, value) { return !value || getFieldValue("new_password") === value ? Promise.resolve() : Promise.reject(new Error("Mật khẩu xác nhận không khớp.")); } })]}><Input.Password autoComplete="new-password" /></Form.Item><Button type="primary" htmlType="submit" loading={busy} block>Đặt lại mật khẩu</Button></Form>}
        <Link href="/login">Quay lại đăng nhập</Link>
      </Space>
    </Card>
  </main>;
}
