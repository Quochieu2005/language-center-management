"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Alert, Button, Card, Space, Tag, Typography, message } from "antd";
import { FacebookFilled, GoogleOutlined, LinkOutlined } from "@ant-design/icons";
import { ApiError } from "@/lib/api/client";
import { authApi, type OAuthProvider } from "@/lib/api/auth";
import { useSession } from "@/lib/auth/session";
import styles from "./SocialAccountConnections.module.scss";

type Connections = Record<OAuthProvider, boolean>;
const providers: { key: OAuthProvider; label: string; icon: ReactNode }[] = [
  { key: "google", label: "Google", icon: <GoogleOutlined /> },
  { key: "facebook", label: "Facebook", icon: <FacebookFilled /> },
];

export function SocialAccountConnections() {
  const { user } = useSession();
  const [connections, setConnections] = useState<Connections | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<OAuthProvider | null>(null);
  const [error, setError] = useState("");
  const [callbackMessage, setCallbackMessage] = useState("");

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError("");
    try {
      const result = await authApi.oauthConnections(user.slug);
      setConnections(result.connections);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Không tải được trạng thái liên kết.");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams(window.location.search);
    const result = params.get("oauth");
    if (result) {
      const messages: Record<string, string> = {
        linked: "Đã liên kết tài khoản thành công.",
        link_conflict: "Tài khoản Google/Facebook này đã liên kết với tài khoản khác hoặc không khớp.",
        session_expired: "Phiên đăng nhập hết hạn. Hãy đăng nhập lại rồi liên kết.",
        invalid: "Yêu cầu liên kết hết hạn hoặc không hợp lệ. Hãy thử lại.",
        cancelled: "Bạn đã hủy liên kết tài khoản.",
        rate_limited: "Bạn thao tác quá nhanh. Vui lòng đợi rồi thử lại.",
        provider_error: "Không xác minh được tài khoản với nhà cung cấp.",
        not_configured: "Nhà cung cấp chưa được cấu hình đầy đủ.",
      };
      window.history.replaceState(null, "", window.location.pathname);
      queueMicrotask(() => {
        if (!cancelled) setCallbackMessage(messages[result] || "Không hoàn tất được liên kết tài khoản.");
      });
    }
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const startLink = async (provider: OAuthProvider) => {
    setBusy(provider);
    setError("");
    try {
      const { authorization_url } = await authApi.startOAuthLink(provider);
      const target = new URL(authorization_url);
      if (target.protocol !== "https:" || !["accounts.google.com", "www.facebook.com"].includes(target.hostname)) {
        throw new Error("Địa chỉ OAuth trả về không hợp lệ.");
      }
      window.location.assign(target.toString());
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "Không bắt đầu được liên kết.");
      setBusy(null);
    }
  };

  return <Card className={styles.card} title="Tài khoản đăng nhập đã liên kết">
    <Space orientation="vertical" size="middle" className={styles.content}>
      <Typography.Text type="secondary">Đăng nhập bằng mật khẩu cấp trước, đổi mật khẩu lần đầu, rồi mới liên kết Google hoặc Facebook. Tài khoản ngoài không tạo mới hồ sơ học viên.</Typography.Text>
      {callbackMessage && <Alert showIcon type={callbackMessage.startsWith("Đã liên kết") ? "success" : "warning"} title={callbackMessage} />}
      {error && <Alert showIcon type="error" title={error} />}
      <div className={styles.providers}>
        {providers.map(({ key, label, icon }) => (
          <div className={styles.provider} key={key}>
            <div className={styles.providerInfo}>
              <span className={styles.icon} aria-hidden="true">{icon}</span>
              <span><strong>{label}</strong><small>{loading ? "Đang kiểm tra..." : connections?.[key] ? "Đã liên kết" : "Chưa liên kết"}</small></span>
            </div>
            {loading ? <Tag>Đang tải</Tag> : connections?.[key]
              ? <Tag color="success">Đã liên kết</Tag>
              : <Button icon={<LinkOutlined />} loading={busy === key} disabled={busy !== null} onClick={() => void startLink(key)}>Liên kết</Button>}
          </div>
        ))}
      </div>
      {!loading && !error && <Button type="link" onClick={() => void load()}>Tải lại trạng thái</Button>}
    </Space>
  </Card>;
}
