"use client";

import { useRef, useState } from "react";
import { Alert, Button, Card, Input, Space, Typography } from "antd";
import { uploadBlogImage } from "@/lib/blogImageUpload";
import BlogContent, { addMarkdownTableRow } from "@/components/web/blog/BlogContent";
import styles from "./BlogContentEditor.module.scss";

const maxContentLength = 20000;
const tableExample = "| Tiêu chí | Nhóm 1 | Nhóm 2 |\n| --- | --- | --- |\n| Format | Nội dung | Nội dung |";
const listExample = "1. Nội dung thứ nhất\n2. Nội dung thứ hai\n3. Nội dung thứ ba";

export default function BlogContentEditor({
  value = "",
  onChange,
  slug,
}: {
  value?: string;
  onChange?: (content: string) => void;
  slug?: string;
}) {
  const [cursorPosition, setCursorPosition] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [imageError, setImageError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const insertImage = async (file?: File) => {
    if (!file) return;
    setUploading(true);
    setImageError("");
    try {
      const result = await uploadBlogImage(slug ?? "", "content", file);
      const alt = file.name.replace(/\.[^.]+$/, "").replace(/[\[\]()]/g, " ").trim().slice(0, 80);
      const markdown = `![${alt}](${result.secure_url})`;
      const at = Math.min(cursorPosition ?? value.length, value.length);
      const before = value.slice(0, at).replace(/\n*$/, "");
      const after = value.slice(at).replace(/^\n*/, "");
      const next = `${before}${before ? "\n\n" : ""}${markdown}${after ? "\n\n" : ""}${after}`;
      if (next.length > maxContentLength) throw new Error("Nội dung vượt quá giới hạn ký tự sau khi chèn ảnh.");
      setCursorPosition(before.length + (before ? 2 : 0) + markdown.length);
      onChange?.(next);
    } catch (reason) {
      setImageError(reason instanceof Error ? reason.message : "Không chèn được ảnh.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };
  const rowAdded = addMarkdownTableRow(value, cursorPosition);
  const append = (example: string) => {
    const separator = !value ? "" : value.endsWith("\n\n") ? "" : value.endsWith("\n") ? "\n" : "\n\n";
    const nextValue = `${value}${separator}${example}`.slice(0, maxContentLength);
    setCursorPosition(nextValue.length);
    onChange?.(nextValue);
  };

  return <div className={styles.editor}>
    <Space wrap>
      <Button htmlType="button" size="small" onClick={() => append(tableExample)}>Chèn bảng mẫu</Button>
      <Button htmlType="button" size="small" disabled={!rowAdded || rowAdded.length > maxContentLength} onClick={() => rowAdded && onChange?.(rowAdded)}>Thêm hàng</Button>
      <Button htmlType="button" size="small" onClick={() => append(listExample)}>Chèn danh sách đánh số</Button>
      <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => void insertImage(event.target.files?.[0])} />
      <Button htmlType="button" size="small" loading={uploading} disabled={!slug} title={slug ? undefined : "Nhập tiêu đề/slug trước"} onClick={() => fileRef.current?.click()}>Chèn ảnh tại con trỏ</Button>
    </Space>
    {imageError && <Alert type="error" showIcon title={imageError} />}
    <Typography.Text className={styles.helpText} type="secondary">
      Có thể viết văn bản thường, tiêu đề bắt đầu bằng ##, danh sách dạng 1. Nội dung hoặc bảng dạng Markdown. Bấm &ldquo;Chèn ảnh tại con trỏ&rdquo; để tải ảnh lên và đặt đúng vị trí đang chọn (ảnh nằm trong cặp ![mô tả](đường dẫn); sửa phần mô tả để đổi chú thích). Đặt con trỏ trong bảng rồi bấm Thêm hàng; nếu chưa chọn bảng, hàng sẽ được thêm vào bảng cuối cùng.
    </Typography.Text>
    <div className={styles.contentColumns}>
      <Input.TextArea className={styles.source} rows={16} maxLength={maxContentLength} showCount value={value}
        onChange={(event) => { setCursorPosition(event.target.selectionStart); onChange?.(event.target.value); }}
        onSelect={(event) => setCursorPosition(event.currentTarget.selectionStart)} />
      <Card size="small" title="Xem trước nội dung" className={styles.previewCard}>
        <div className={styles.previewBody}>
          {value.trim() ? <BlogContent content={value} compact /> : <Typography.Text type="secondary">Nội dung xem trước sẽ hiện ở đây.</Typography.Text>}
        </div>
      </Card>
    </div>
  </div>;
}
