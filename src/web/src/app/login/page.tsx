"use client";

import Link from "next/link";
import { Alert, Button, Form, Input, Typography } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/auth";
import { homeForRole, useSession } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/client";
import AuthPageShell from "@/components/web/auth/AuthPageShell";
import styles from "@/components/web/auth/AuthForm.module.scss";

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
  return <AuthPageShell eyebrow="KHU VỰC NHÂN SỰ" title="Chào mừng bạn trở lại." description="Đăng nhập bằng tài khoản do trung tâm cấp để tiếp tục công việc.">
    <div className={styles.heading}>
      <span className={styles.kicker}>TÀI KHOẢN NỘI BỘ</span>
      <Typography.Title level={2}>Đăng nhập</Typography.Title>
      <Typography.Paragraph>Dùng email hoặc tên đăng nhập đã được cấp.</Typography.Paragraph>
    </div>
    {error && <Alert className={styles.error} type="error" showIcon title={error} />}
    <Form className={styles.form} layout="vertical" onFinish={submit} requiredMark={false}>
      <Form.Item name="identifier" label="Email hoặc tên đăng nhập" rules={[{ required: true, whitespace: true, message: "Nhập email hoặc tên đăng nhập." }]}>
        <Input autoComplete="username" prefix={<UserOutlined />} maxLength={254} size="large" />
      </Form.Item>
      <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, message: "Nhập mật khẩu." }]}>
        <Input.Password autoComplete="current-password" prefix={<LockOutlined />} maxLength={128} size="large" />
      </Form.Item>
      <div className={styles.formMeta}><span>Phiên đăng nhập an toàn</span><Link href="/forgot-password">Quên mật khẩu?</Link></div>
      <Button className={styles.submit} type="primary" htmlType="submit" loading={busy} block size="large">Đăng nhập <span aria-hidden="true">→</span></Button>
    </Form>
    <div className={styles.securityNote}><span aria-hidden="true">i</span><span>Chỉ tài khoản nội bộ được trung tâm cấp mới có thể đăng nhập.</span></div>
  </AuthPageShell>;
}
