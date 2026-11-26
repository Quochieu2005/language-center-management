"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Button, Form, Input, Typography } from "antd";
import { authApi } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import AuthPageShell from "@/components/web/auth/AuthPageShell";
import styles from "@/components/web/auth/AuthForm.module.scss";

type Values = { full_name: string; email: string; password: string; confirm_password: string };

export default function RegisterPage() {
  const [ready, setReady] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let current = true;
    authApi.registrationSites().then((result) => { if (current) { setReady(result.registration_ready); setError(""); } })
      .catch(() => { if (current) setError("Chưa kiểm tra được trạng thái đăng ký. Vui lòng thử lại."); });
    return () => { current = false; };
  }, [attempt]);
  const submit = async (values: Values) => {
    setBusy(true); setError("");
    try {
      const result = await authApi.register(values);
      setSuccess(result.detail);
    } catch (reason) {
      const problem = reason instanceof ApiError ? reason : null;
      const fields = problem && Object.entries(problem.payload).filter(([, value]) => Array.isArray(value)).map(([, value]) => (value as string[]).join(" ")).join(" ");
      setError(fields || (reason instanceof Error ? reason.message : "Không kết nối được dịch vụ đăng ký."));
    } finally { setBusy(false); }
  };
  return <AuthPageShell eyebrow="BẮT ĐẦU HỌC TẬP" title="Tạo tài khoản miễn phí." description="Bạn có thể đăng nhập và chọn khóa học sau. Đăng ký tài khoản chưa phát sinh học phí.">
    <div className={styles.heading}><Typography.Title level={2}>Đăng ký tài khoản</Typography.Title><Typography.Paragraph>Chỉ cần họ tên, email và mật khẩu. Bạn chọn khóa học và cơ sở khi đăng ký lớp.</Typography.Paragraph></div>
    {success ? <><Alert type="success" showIcon title={success} /><p><Link href="/login">Đăng nhập ngay →</Link></p></> : <>
      {error && <Alert className={styles.error} type="error" showIcon title={error} />}
      {ready === false && <Alert type="info" showIcon title="Đăng ký tài khoản đang tạm ngưng. Vui lòng quay lại sau hoặc liên hệ trung tâm." />}
      {ready === null && <Button onClick={() => setAttempt((value) => value + 1)}>Kiểm tra lại</Button>}
      <Form className={styles.form} layout="vertical" onFinish={submit} requiredMark={false} disabled={busy}>
        <Form.Item name="full_name" label="Họ và tên" rules={[{ required: true, whitespace: true, message: "Nhập họ tên." }]}><Input autoComplete="name" maxLength={150} size="large" /></Form.Item>
        <Form.Item name="email" label="Email" rules={[{ required: true, type: "email", message: "Nhập email hợp lệ." }]}><Input type="email" autoComplete="email" maxLength={254} size="large" /></Form.Item>
        <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, min: 12, message: "Dùng ít nhất 12 ký tự." }]}><Input.Password autoComplete="new-password" minLength={12} maxLength={128} size="large" /></Form.Item>
        <Form.Item name="confirm_password" label="Xác nhận mật khẩu" dependencies={["password"]} rules={[{ required: true, message: "Nhập lại mật khẩu." }, ({ getFieldValue }) => ({ validator: (_, value) => !value || getFieldValue("password") === value ? Promise.resolve() : Promise.reject(new Error("Mật khẩu không khớp.")) })]}><Input.Password autoComplete="new-password" maxLength={128} size="large" /></Form.Item>
        <Button className={styles.submit} type="primary" htmlType="submit" loading={busy} disabled={!ready} size="large" block>Tạo tài khoản miễn phí</Button>
      </Form>
    </>}
    <p>Đã có tài khoản? <Link href="/login">Đăng nhập</Link></p>
  </AuthPageShell>;
}
