"use client";

import Link from "next/link";
import { Alert, App, Button, Form, Input, Space, Typography } from "antd";
import { FacebookFilled, GoogleOutlined, LockOutlined, UserOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/auth";
import { homeForRole, useSession } from "@/lib/auth/session";
import { ApiError, apiUrl } from "@/lib/api/client";
import AuthPageShell from "@/components/web/auth/AuthPageShell";
import styles from "@/components/web/auth/AuthForm.module.scss";

export default function LoginPage() {
  const [busy, setBusy] = useState(false);
  const [socialBusy, setSocialBusy] = useState("");
  const [error, setError] = useState("");
  const { message } = App.useApp();
  const { signIn } = useSession();
  const router = useRouter();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("oauth");
    if (!result) return;
    window.history.replaceState(null, "", "/login");
    if (result === "success") {
      void Promise.resolve().then(() => {
        setSocialBusy("session");
        return authApi.session();
      }).then(({ user }) => {
        signIn(user);
        if (user.must_change_password) message.info("Tài khoản đang dùng mật khẩu do trung tâm cấp. Bạn có thể đổi mật khẩu khi thuận tiện.");
        router.replace(homeForRole(user.role));
      }).catch(() => setError("Không xác minh được phiên Google/Facebook. Hãy đăng nhập lại bằng tài khoản được cấp."))
        .finally(() => setSocialBusy(""));
      return;
    }
    const messages: Record<string, string> = {
      not_linked: "Tài khoản này chưa được liên kết. Hãy đăng nhập bằng tài khoản được trung tâm cấp.",
      not_configured: "Đăng nhập Google/Facebook chưa được cấu hình đầy đủ.",
      cancelled: "Bạn đã hủy đăng nhập bằng nhà cung cấp.",
      rate_limited: "Bạn thao tác quá nhanh. Vui lòng đợi rồi thử lại.",
      provider_error: "Không xác minh được tài khoản với nhà cung cấp. Vui lòng thử lại.",
      invalid: "Yêu cầu đăng nhập đã hết hạn hoặc không hợp lệ. Hãy bắt đầu lại.",
      session_expired: "Phiên đã hết hạn. Hãy đăng nhập lại rồi thử liên kết.",
    };
    queueMicrotask(() => setError(messages[result] || "Đăng nhập ngoài không thành công."));
  }, [message, router, signIn]);

  const beginSocialLogin = (provider: "google" | "facebook") => {
    setSocialBusy(provider);
    window.location.assign(apiUrl(authApi.oauthLoginUrl(provider)));
  };
  const submit = async (values: { identifier: string; password: string }) => {
    setBusy(true); setError("");
    try {
      const result = await authApi.login(values.identifier, values.password);
      signIn(result.user);
      if (result.user.must_change_password) message.info("Tài khoản đang dùng mật khẩu do trung tâm cấp. Bạn có thể đổi mật khẩu khi thuận tiện.");
      router.replace(homeForRole(result.user.role));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Không kết nối được API. Kiểm tra máy chủ và địa chỉ API.");
    } finally { setBusy(false); }
  };
  return <AuthPageShell eyebrow="CỔNG ĐĂNG NHẬP" title="Chào mừng bạn trở lại." description="Dùng mật khẩu được cấp hoặc tài khoản Google/Facebook đã liên kết để tiếp tục.">
    <div className={styles.heading}>
      <span className={styles.kicker}>TÀI KHOẢN NỘI BỘ</span>
      <Typography.Title level={2}>Đăng nhập</Typography.Title>
      <Typography.Paragraph>Dùng email hoặc tên đăng nhập đã được cấp.</Typography.Paragraph>
    </div>
    {error && <Alert className={styles.error} type="error" showIcon title={error} />}
    <Form className={styles.form} layout="vertical" onFinish={submit} requiredMark={false} disabled={Boolean(socialBusy)}>
      <Form.Item name="identifier" label="Email hoặc tên đăng nhập" rules={[{ required: true, whitespace: true, message: "Nhập email hoặc tên đăng nhập." }]}>
        <Input autoComplete="username" prefix={<UserOutlined />} maxLength={254} size="large" />
      </Form.Item>
      <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, message: "Nhập mật khẩu." }]}>
        <Input.Password autoComplete="current-password" prefix={<LockOutlined />} maxLength={128} size="large" />
      </Form.Item>
      <div className={styles.formMeta}><span>Phiên đăng nhập an toàn</span><Link href="/forgot-password">Quên mật khẩu?</Link></div>
      <Button className={styles.submit} type="primary" htmlType="submit" loading={busy} block size="large">Đăng nhập <span aria-hidden="true">→</span></Button>
    </Form>
    <div className={styles.socialLogin}>
      <span>Hoặc tiếp tục với tài khoản đã liên kết</span>
      <Space wrap>
        <Button icon={<GoogleOutlined />} loading={socialBusy === "google" || socialBusy === "session"} disabled={Boolean(socialBusy)} onClick={() => beginSocialLogin("google")}>Google</Button>
        <Button icon={<FacebookFilled />} loading={socialBusy === "facebook" || socialBusy === "session"} disabled={Boolean(socialBusy)} onClick={() => beginSocialLogin("facebook")}>Facebook</Button>
      </Space>
    </div>
    <div className={styles.securityNote}><span aria-hidden="true">i</span><span>Google/Facebook chỉ dùng cho học viên đã liên kết trước đó; không tự tạo tài khoản mới.</span></div>
  </AuthPageShell>;
}
