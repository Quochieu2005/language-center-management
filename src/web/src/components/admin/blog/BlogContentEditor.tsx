"use client";

import { useState } from "react";
import { Button, Card, Input, Space, Typography } from "antd";
import BlogContent, { addMarkdownTableRow } from "@/components/web/blog/BlogContent";
import styles from "./BlogContentEditor.module.scss";

const maxContentLength = 20000;
const tableExample = "| Tiêu chí | Nhóm 1 | Nhóm 2 |\n| --- | --- | --- |\n| Format | Nội dung | Nội dung |";
const listExample = "1. Nội dung thứ nhất\n2. Nội dung thứ hai\n3. Nội dung thứ ba";

export default function BlogContentEditor({
  value = "",
  onChange,
}: {
  value?: string;
  onChange?: (content: string) => void;
}) {
  const [cursorPosition, setCursorPosition] = useState<number | null>(null);
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
    </Space>
    <Typography.Text className={styles.helpText} type="secondary">
      Có thể viết văn bản thường, tiêu đề bắt đầu bằng ##, danh sách dạng 1. Nội dung hoặc bảng dạng Markdown. Đặt con trỏ trong bảng rồi bấm Thêm hàng; nếu chưa chọn bảng, hàng sẽ được thêm vào bảng cuối cùng.
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
