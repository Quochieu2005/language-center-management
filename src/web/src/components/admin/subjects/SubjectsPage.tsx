"use client";

import { useState } from "react";
import { Alert, Button, Card, Form, Input, Space, Typography, message } from "antd";
import { adminApi } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

export default function SubjectsPage() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState("");
  const submit = async (values: { slug: string; ten_mon: string; mo_ta?: string }) => {
    setBusy(true); setError(""); setResult(null);
    try { const response = await adminApi.updateSubject(values.slug, { ten_mon: values.ten_mon, mo_ta: values.mo_ta }); setResult(response); message.success("Đã gửi cập nhật danh mục dùng chung tới API."); }
    catch (reason) {
      if (reason instanceof ApiError && Object.keys(reason.payload).length) setResult(reason.payload);
      setError(reason instanceof Error ? reason.message : "Không cập nhật được môn học.");
    } finally { setBusy(false); }
  };
  return <Card title="Cập nhật môn học dùng chung">
    <Alert type="info" showIcon title="Backend hiện có PATCH theo slug nhưng chưa có API GET để tải danh sách môn học. Nhập slug chính xác từ dữ liệu đã có; API chịu trách nhiệm đồng bộ bản sao và trả trạng thái từng site." style={{ marginBottom: 20 }} />
    {error && <Alert type="warning" showIcon title={error} style={{ marginBottom: 16 }} />}
    <Form layout="vertical" onFinish={submit} style={{ maxWidth: 560 }}><Form.Item name="slug" label="Slug môn học" rules={[{ required: true, max: 160 }]}><Input maxLength={160} /></Form.Item><Form.Item name="ten_mon" label="Tên môn học mới" rules={[{ required: true, max: 120 }]}><Input maxLength={120} /></Form.Item><Form.Item name="mo_ta" label="Mô tả"><Input.TextArea maxLength={500} rows={4} /></Form.Item><Button type="primary" htmlType="submit" loading={busy}>Cập nhật và đồng bộ</Button></Form>
    {result !== null && <Space direction="vertical" style={{ width: "100%", marginTop: 24 }}><Typography.Title level={5}>Phản hồi API</Typography.Title><pre style={{ whiteSpace: "pre-wrap", overflow: "auto" }}>{JSON.stringify(result, null, 2)}</pre></Space>}
  </Card>;
}
