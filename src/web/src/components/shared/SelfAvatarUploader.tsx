"use client";

import { useRef, useState } from "react";
import { Alert, Button, Space } from "antd";
import { message } from "@/lib/ui/message";
import { UploadOutlined } from "@ant-design/icons";
import { authApi, type AvatarUploadIntent } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

type PendingAvatar = { intent_token: string; public_id: string };

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;

type AvatarApi = {
  createIntent: (slug: string) => Promise<AvatarUploadIntent>;
  complete: (slug: string, body: { intent_token: string; public_id: string }) => Promise<{ avatar_secure_url: string }>;
};

/** Account photo (staff, teachers); students pass their own profile-photo API instead. */
const accountAvatarApi: AvatarApi = {
  createIntent: authApi.createAvatarUploadIntent,
  complete: authApi.completeAvatarUpload,
};

type Props = {
  slug: string | undefined;
  hasAvatar?: boolean;
  onUploaded: (url: string | null) => void;
  api?: AvatarApi;
};

/**
 * Self-service avatar upload: signed intent from the API, direct upload to Cloudinary,
 * then the API completes it. A failed completion keeps the uploaded asset so the user
 * can resume instead of uploading again.
 */
export function SelfAvatarUploader({ slug, hasAvatar = false, onUploaded, api = accountAvatarApi }: Props) {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<PendingAvatar | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const complete = async (intentToken: string, publicId: string) => {
    if (!slug) return;
    setLoading(true);
    setError("");
    try {
      const result = await api.complete(slug, { intent_token: intentToken, public_id: publicId });
      onUploaded(result.avatar_secure_url);
      setPending(null);
      message.success("Đã cập nhật ảnh đại diện.");
    } catch (reason) {
      const detail = reason instanceof Error ? reason.message : "Chưa đồng bộ được ảnh qua các cơ sở.";
      setError(`${detail} Bạn có thể bấm tiếp tục đồng bộ ảnh để thử lại.`);
      const final = reason instanceof ApiError && [400, 401, 403, 404, 409].includes(reason.status);
      setPending(final ? null : { intent_token: intentToken, public_id: publicId });
    } finally {
      setLoading(false);
    }
  };

  const choose = async (file?: File) => {
    if (!file || !slug) return;
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError("Chỉ nhận ảnh JPG, PNG hoặc WebP.");
      return;
    }
    if (file.size < 1 || file.size > MAX_BYTES) {
      setError("Ảnh phải có dung lượng tối đa 5 MB.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const intent = await api.createIntent(slug);
      const body = new FormData();
      body.append("file", file);
      body.append("api_key", intent.api_key);
      Object.entries(intent.fields).forEach(([key, value]) => body.append(key, value));
      const response = await fetch(intent.upload_url, { method: "POST", body, cache: "no-store" });
      const uploaded = (await response.json().catch(() => null)) as { public_id?: unknown } | null;
      if (!response.ok || typeof uploaded?.public_id !== "string") {
        throw new Error("Cloudinary không nhận được ảnh. Hãy kiểm tra cấu hình và thử lại.");
      }
      const next = { intent_token: intent.intent_token, public_id: uploaded.public_id };
      setPending(next);
      await complete(next.intent_token, next.public_id);
    } catch (reason) {
      const detail = reason instanceof Error ? reason.message : "Không tải được ảnh đại diện.";
      setError(detail);
      message.error(detail);
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <Space orientation="vertical" size={8}>
      <Space wrap>
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(event) => void choose(event.target.files?.[0])}
        />
        <Button icon={<UploadOutlined />} loading={loading} disabled={Boolean(pending) || !slug} onClick={() => inputRef.current?.click()}>
          {hasAvatar ? "Đổi ảnh đại diện" : "Tải ảnh lên"}
        </Button>
        {pending && (
          <Button loading={loading} onClick={() => void complete(pending.intent_token, pending.public_id)}>
            Tiếp tục đồng bộ ảnh
          </Button>
        )}
      </Space>
      {error && <Alert type="error" showIcon title={error} />}
    </Space>
  );
}
