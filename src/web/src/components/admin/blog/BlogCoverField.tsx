"use client";

import { useRef, useState } from "react";
import { Alert, Button, Space } from "antd";
import { DeleteOutlined, UploadOutlined } from "@ant-design/icons";
import { uploadBlogImage } from "@/lib/blogImageUpload";
import styles from "./BlogCoverField.module.scss";

export type BlogCover = { public_id: string; url: string } | null;

/** Cover picture of an article: uploaded under `<root>/blog/bia/<slug>-dd-mm-yyyy` on Cloudinary. */
export default function BlogCoverField({ value = null, onChange, slug }: {
  value?: BlogCover; onChange?: (cover: BlogCover) => void; slug?: string;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const choose = async (file?: File) => {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const result = await uploadBlogImage(slug ?? "", "cover", file);
      onChange?.({ public_id: result.public_id, url: result.secure_url });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được ảnh bìa.");
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return <div className={styles.field}>
    {value
      // eslint-disable-next-line @next/next/no-img-element
      ? <img className={styles.preview} src={value.url} alt="Ảnh bìa bài viết" />
      : <div className={styles.empty}>Chưa có ảnh bìa — trang Blog sẽ dùng nền màu mặc định.</div>}
    <Space wrap>
      <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => void choose(event.target.files?.[0])} />
      <Button htmlType="button" icon={<UploadOutlined />} loading={loading} disabled={!slug} onClick={() => inputRef.current?.click()}>
        {value ? "Đổi ảnh bìa" : "Chọn ảnh bìa"}
      </Button>
      {value && <Button htmlType="button" danger icon={<DeleteOutlined />} onClick={() => onChange?.(null)}>Bỏ ảnh bìa</Button>}
      {!slug && <span className={styles.hint}>Nhập tiêu đề/slug trước khi chọn ảnh.</span>}
    </Space>
    {error && <Alert type="error" showIcon title={error} />}
  </div>;
}
