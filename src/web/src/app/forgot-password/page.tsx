"use client";

import Link from "next/link";
import { Alert, Button, Form, Input, Typography, message } from "antd";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import AuthPageShell from "@/components/web/auth/AuthPageShell";
import styles from "@/components/web/auth/AuthForm.module.scss";

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
  return <AuthPageShell eyebrow="HỖ TRỢ TÀI KHOẢN" title="Lấy lại quyền truy cập." description="Dùng địa chỉ email đã đăng ký với trung tâm để xác minh tài khoản.">
    <div className={styles.heading}>
      <span className={styles.kicker}>{sent ? "BƯỚC 2 / 2" : "BƯỚC 1 / 2"}</span>
      <Typography.Title level={2}>{sent ? "Nhập mã xác minh" : "Khôi phục mật khẩu"}</Typography.Title>
      <Typography.Paragraph>{sent ? "Nếu email thuộc tài khoản đủ điều kiện, mã sẽ được gửi tới hộp thư. Mã có hiệu lực 2 phút." : "Nhập email tài khoản. Hệ thống luôn trả lời theo cùng một cách để bảo vệ thông tin của bạn."}</Typography.Paragraph>
    </div>
    {error && <Alert className={styles.error} type="error" showIcon title={error} />}
    {!sent ? <Form className={styles.form} layout="vertical" onFinish={forgot} requiredMark={false}>
      <Form.Item name="email" label="Email tài khoản" rules={[{ required: true, type: "email", message: "Nhập địa chỉ email hợp lệ." }]}>
        <Input autoComplete="email" maxLength={254} size="large" />
      </Form.Item>
      <Button className={styles.submit} type="primary" htmlType="submit" loading={busy} block size="large">Gửi mã xác minh <span aria-hidden="true">→</span></Button>
    </Form> : <Form className={styles.form} layout="vertical" onFinish={reset} requiredMark={false}>
      <Alert className={styles.info} type="info" showIcon title="Kiểm tra cả thư mục thư rác nếu bạn chưa thấy email." />
      <Form.Item name="otp" label="Mã OTP 6 chữ số" rules={[{ required: true, len: 6, message: "Nhập đủ 6 chữ số." }]}>
        <Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} size="large" />
      </Form.Item>
      <Form.Item name="new_password" label="Mật khẩu mới" rules={[{ required: true, min: 12, max: 128, message: "Mật khẩu cần có từ 12 đến 128 ký tự." }]}>
        <Input.Password autoComplete="new-password" maxLength={128} size="large" />
      </Form.Item>
      <Form.Item name="confirm_password" label="Nhập lại mật khẩu" dependencies={["new_password"]} rules={[{ required: true, message: "Nhập lại mật khẩu mới." }, ({ getFieldValue }) => ({ validator(_, value) { return !value || getFieldValue("new_password") === value ? Promise.resolve() : Promise.reject(new Error("Mật khẩu xác nhận không khớp.")); } })]}>
        <Input.Password autoComplete="new-password" maxLength={128} size="large" />
      </Form.Item>
      <Button className={styles.submit} type="primary" htmlType="submit" loading={busy} block size="large">Đặt lại mật khẩu <span aria-hidden="true">→</span></Button>
    </Form>}
    <Link className={styles.backLink} href="/login">← Quay lại đăng nhập</Link>
  </AuthPageShell>;
}
