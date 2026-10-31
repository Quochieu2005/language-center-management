"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, message } from "antd";
import { academicsApi, type TransferRow } from "@/lib/api/academics";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";

export default function TransfersPage() {
  const { user } = useSession();
  const [rows, setRows] = useState<TransferRow[]>([]);
  const [activeSites, setActiveSites] = useState<string[]>([]);
  const [missing, setMissing] = useState<string[]>([]);
  const [complete, setComplete] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [requestOpen, setRequestOpen] = useState(false);
  const [decision, setDecision] = useState<{ row: TransferRow; value: "approve" | "reject" } | null>(null);
  const [form] = Form.useForm();
  const [decisionForm] = Form.useForm();
  const isBig = user?.role === "admin_big";
  const load = useCallback(async () => {
    try {
      const result = await academicsApi.transfers();
      setRows(result.results); setActiveSites(result.site_codes); setMissing(result.missing_sites); setComplete(result.complete); setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được đề nghị chuyển.");
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) {
        const payload = reason.payload as unknown as { results: TransferRow[]; site_codes?: string[]; missing_sites?: string[]; complete?: boolean };
        setRows(payload.results); setActiveSites(payload.site_codes || []); setMissing(payload.missing_sites || []); setComplete(payload.complete === true);
      }
    }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);
  const create = async (values: { student_slug: string; target_site: string; reason: string }) => {
    try { await academicsApi.requestTransfer(values); message.success("Đã gửi đề nghị tại cơ sở nguồn để Admin Big duyệt."); setRequestOpen(false); form.resetFields(); void load(); }
    catch (reason) { message.error(asMessage(reason)); }
  };
  const decide = async (values: { reason?: string }) => {
    if (!decision) return;
    try { const result = await academicsApi.decideTransfer(decision.row.source_site, decision.row.transfer_id, { decision: decision.value, reason: values.reason }); message.success(decision.value === "approve" ? (result.complete ? "Đã duyệt và điều phối chuyển." : "Đã duyệt; giao dịch còn bước chờ phục hồi.") : "Đã từ chối đề nghị."); setDecision(null); decisionForm.resetFields(); void load(); }
    catch (reason) { message.error(asMessage(reason)); }
  };
  const retry = async (row: TransferRow) => {
    try { const result = await academicsApi.retryTransfer(row.source_site, row.transfer_id); message.success(result.complete ? "Đã hoàn tất khôi phục giao dịch." : "Giao dịch vẫn chưa hoàn tất; kiểm tra site thiếu rồi thử lại."); void load(); }
    catch (reason) { message.error(asMessage(reason)); }
  };
  const columns = [
    { title: "Mã", dataIndex: "transfer_id" }, { title: "Học viên", dataIndex: "student_name" }, { title: "Từ", dataIndex: "source_site" }, { title: "Đến", dataIndex: "target_site" },
    { title: "Lý do", dataIndex: "reason" }, { title: "Trạng thái", dataIndex: "status", render: (value: string) => <Tag color={value === "hoan_tat" ? "green" : value === "that_bai" ? "red" : "gold"}>{value}</Tag> },
    { title: "Thao tác", render: (_: unknown, row: TransferRow) => <Space wrap>{isBig && row.status === "cho_duyet" && <><Button size="small" type="primary" onClick={() => setDecision({ row, value: "approve" })}>Duyệt</Button><Button size="small" danger onClick={() => setDecision({ row, value: "reject" })}>Từ chối</Button></>}{isBig && ["dang_xu_ly", "that_bai"].includes(row.status) && <Popconfirm title="Tiếp tục tiến trình đã duyệt?" onConfirm={() => void retry(row)}><Button size="small">Thử phục hồi</Button></Popconfirm>}</Space> },
  ];
  return <Card title="Chuyển cơ sở" extra={!isBig && user?.role === "admin_small" ? <Button type="primary" onClick={() => setRequestOpen(true)}>Tạo đề nghị</Button> : null}>
    <Alert type="info" showIcon title={isBig ? "Admin Big xem đề nghị bằng Global Query; duyệt/từ chối được ghi tại site nguồn. Chuyển hồ sơ chạy qua Coordinator và có thể cần phục hồi." : "Admin Small chỉ tạo đề nghị cho học viên ở cơ sở mình; chưa có dữ liệu nào chuyển đi trước khi Admin Big duyệt."} style={{ marginBottom: 16 }} />
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    {!complete && <Alert type="warning" showIcon title={`Dữ liệu chưa đầy đủ. Site không phản hồi: ${missing.join(", ") || "không rõ"}`} style={{ marginBottom: 16 }} />}
    <Table rowKey={(row) => `${row.source_site}:${row.transfer_id}`} loading={loading} columns={columns} dataSource={rows} scroll={{ x: 950 }} />
    <Modal title="Tạo đề nghị chuyển cơ sở" open={requestOpen} onCancel={() => setRequestOpen(false)} footer={null} destroyOnClose><Form form={form} layout="vertical" onFinish={create}><Form.Item name="student_slug" label="Slug học viên" rules={[{ required: true, max: 160 }]}><Input maxLength={160} /></Form.Item><Form.Item name="target_site" label="Cơ sở nhận" rules={[{ required: true }]}><Select options={activeSites.filter((code) => code !== user?.site_code).map((code) => ({ value: code, label: code }))} /></Form.Item><Form.Item name="reason" label="Lý do" rules={[{ required: true, max: 500 }]}><Input.TextArea maxLength={500} rows={4} /></Form.Item><Button type="primary" htmlType="submit" block>Gửi Admin Big duyệt</Button></Form></Modal>
    <Modal title={decision?.value === "approve" ? "Duyệt đề nghị" : "Từ chối đề nghị"} open={Boolean(decision)} onCancel={() => setDecision(null)} footer={null} destroyOnClose><Form form={decisionForm} layout="vertical" onFinish={decide}>{decision?.value === "reject" && <Form.Item name="reason" label="Lý do từ chối" rules={[{ required: true, max: 500 }]}><Input.TextArea maxLength={500} rows={3} /></Form.Item>}<Button type="primary" danger={decision?.value === "reject"} htmlType="submit" block>{decision?.value === "approve" ? "Duyệt và điều phối" : "Từ chối"}</Button></Form></Modal>
  </Card>;
}

function asMessage(error: unknown) { return error instanceof Error ? error.message : "Yêu cầu API thất bại."; }
