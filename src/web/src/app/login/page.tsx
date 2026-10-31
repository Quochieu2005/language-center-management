"use client";

import Link from "next/link";
import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/auth";
import { homeForRole, useSession } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/client";

export default function LoginPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { signIn } = useSession();
  const router = useRouter();
  const submit = async (values: { identifier: string; password: string }) => {
    setBusy(true); setError("");
    try {
      const result = await authApi.login(values.identifier, values.password);
      signIn(result.user);
      router.replace(result.user.must_change_password ? "/password/change" : homeForRole(result.user.role));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Không kết nối được API. Kiểm tra máy chủ và địa chỉ API.");
    } finally { setBusy(false); }
  };
  return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20 }}>
    <Card style={{ width: "min(100%, 440px)" }}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <div><Typography.Title level={2}>Đăng nhập</Typography.Title><Typography.Text type="secondary">Dùng tài khoản được trung tâm cấp.</Typography.Text></div>
        {error && <Alert type="error" showIcon title={error} />}
        <Form layout="vertical" onFinish={submit} requiredMark={false}>
          <Form.Item name="identifier" label="Email hoặc tên đăng nhập" rules={[{ required: true, whitespace: true }]}><Input autoComplete="username" prefix={<UserOutlined />} maxLength={254} /></Form.Item>
          <Form.Item name="password" label="Mật khẩu" rules={[{ required: true }]}><Input.Password autoComplete="current-password" prefix={<LockOutlined />} maxLength={128} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={busy} block>Đăng nhập</Button>
        </Form>
        <Link href="/forgot-password">Quên mật khẩu?</Link>
      </Space>
    </Card>
  </main>;
}
