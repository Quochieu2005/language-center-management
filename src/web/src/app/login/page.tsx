"use client";

import Link from "next/link";
import { Alert, Button, Form, Input, Space, Typography } from "antd";
import { FacebookFilled, GoogleOutlined, LockOutlined, UserOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./page.module.scss";
import { authApi } from "@/lib/api/auth";
import { homeForRole, useSession } from "@/lib/auth/session";
import { ApiError, apiUrl } from "@/lib/api/client";

export default function LoginPage() {
  const [busy, setBusy] = useState(false);
  const [socialBusy, setSocialBusy] = useState("");
  const [error, setError] = useState("");
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
        router.replace(user.must_change_password ? "/password/change" : homeForRole(user.role));
      }).catch(() => setError("Không xác minh được phiên Google/Facebook. Hãy đăng nhập lại bằng tài khoản được cấp."))
        .finally(() => setSocialBusy(""));
      return;
    }
    const messages: Record<string, string> = {
      not_linked: "Tài khoản này chưa được học viên liên kết. Hãy đăng nhập bằng mật khẩu được cấp rồi liên kết trong cổng học viên.",
      not_configured: "Đăng nhập Google/Facebook chưa được cấu hình đầy đủ.",
      cancelled: "Bạn đã hủy đăng nhập bằng nhà cung cấp.",
      rate_limited: "Bạn thao tác quá nhanh. Vui lòng đợi rồi thử lại.",
      provider_error: "Không xác minh được tài khoản với nhà cung cấp. Vui lòng thử lại.",
      invalid: "Yêu cầu đăng nhập đã hết hạn hoặc không hợp lệ. Hãy bắt đầu lại.",
      session_expired: "Phiên đã hết hạn. Hãy đăng nhập bằng mật khẩu rồi thử liên kết lại.",
    };
    const callbackError = messages[result] || "Đăng nhập ngoài không thành công.";
    queueMicrotask(() => setError(callbackError));
  }, [router, signIn]);

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
  const beginSocialLogin = (provider: "google" | "facebook") => {
    setSocialBusy(provider);
    window.location.assign(apiUrl(authApi.oauthLoginUrl(provider)));
  };
  return <main className={styles.page}>
    <div className={styles.frame}>
      <Link className={styles.brand} href="/" aria-label="Polyglot, về trang chủ">
        <span className={styles.brandMark} aria-hidden="true">P</span>
        <span><strong>POLYGLOT</strong><small>TRUNG TÂM ĐÀO TẠO NGOẠI NGỮ</small></span>
      </Link>
      <section className={styles.card} aria-labelledby="login-title">
      <Space orientation="vertical" size="large" className={styles.content}>
        <div className={styles.heading}><Typography.Title id="login-title" level={2}>Đăng nhập</Typography.Title><Typography.Text type="secondary">Dùng tài khoản được trung tâm cấp.</Typography.Text></div>
        {error && <Alert type="error" showIcon title={error} />}
        <Form layout="vertical" onFinish={submit} requiredMark={false} disabled={Boolean(socialBusy)}>
          <Form.Item name="identifier" label="Email hoặc tên đăng nhập" rules={[{ required: true, whitespace: true }]}><Input autoComplete="username" prefix={<UserOutlined />} maxLength={254} /></Form.Item>
          <Form.Item name="password" label="Mật khẩu" rules={[{ required: true }]}><Input.Password autoComplete="current-password" prefix={<LockOutlined />} maxLength={128} /></Form.Item>
          <Button className={styles.submit} type="primary" htmlType="submit" loading={busy} block>Đăng nhập</Button>
        </Form>
        <div className={styles.social}>
          <Space className={styles.socialButtons}>
            <Button icon={<GoogleOutlined />} loading={socialBusy === "google" || socialBusy === "session"} disabled={Boolean(socialBusy)} onClick={() => beginSocialLogin("google")}>Google</Button>
            <Button icon={<FacebookFilled />} loading={socialBusy === "facebook" || socialBusy === "session"} disabled={Boolean(socialBusy)} onClick={() => beginSocialLogin("facebook")}>Facebook</Button>
          </Space>
        </div>
        <div className={styles.accountLinks}>
          <Link className={styles.forgot} href="/forgot-password">Quên mật khẩu?</Link>
          <Link className={styles.register} href="/contact">Chưa đăng ký khóa học? Đăng ký tư vấn</Link>
        </div>
      </Space>
      </section>
      <p className={styles.footer}>© {new Date().getFullYear()} Polyglot · Hệ thống quản lý trung tâm ngoại ngữ</p>
    </div>
  </main>;
}
