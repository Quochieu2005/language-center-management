"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, message } from "antd";
import { academicsApi, type TuitionRow } from "@/lib/api/academics";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

export default function TuitionPage() {
  const { user } = useSession();
  const { selectedSite } = useSiteScope();
  const site = user?.role === "admin_big" ? selectedSite : user?.site_code || null;
  const canCollect = user?.role === "ke_toan";
  const canManagePlan = ["admin_big", "admin_small", "ke_toan"].includes(user?.role || "");
  const canSendReminder = canManagePlan;
  const [rows, setRows] = useState<TuitionRow[]>([]);
  const [active, setActive] = useState<TuitionRow | null>(null);
  const [modal, setModal] = useState<"receipt" | "plan" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [receiptForm] = Form.useForm();
  const [planForm] = Form.useForm();
  const load = useCallback(async () => {
    if (!site) return;
    try { const result = await academicsApi.tuition(site); setRows(result.results); setError(""); }
    catch (reason) { setError(toMessage(reason)); }
    finally { setLoading(false); }
  }, [site]);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);
  const collect = async (values: { amount: number; payment_method: "tien_mat" | "chuyen_khoan" | "the"; note?: string }) => {
    if (!site || !active) return;
    try {
      const key = crypto.randomUUID().replaceAll("-", "").slice(0, 24);
      const result = await academicsApi.collectTuition(active.tuition_id, site, { ...values, idempotency_key: key });
      const email = result.invoice_email && typeof result.invoice_email === "object" ? String((result.invoice_email as Record<string, unknown>).status || "") : "";
      message.success(email === "sent" || email === "already_sent" ? "Đã ghi nhận khoản thu và gửi hóa đơn qua email." : "Đã ghi nhận khoản thu. Trạng thái gửi email được API trả về; kiểm tra dữ liệu trước khi thu lại.");
      setModal(null); setActive(null); receiptForm.resetFields(); void load();
    } catch (reason) { message.error(`${toMessage(reason)} Nếu kết quả không rõ, tải lại danh sách/tra cứu phiếu trước khi gửi khoản thu mới.`); }
  };
  const savePlan = async (values: { payment_mode: "full" | "monthly"; installment_count?: 3 | 6 | 9 | 12; first_due_date: string }) => {
    if (!site || !active) return;
    try { await academicsApi.saveInstallments(active.tuition_id, site, values); message.success("Đã lưu kế hoạch đóng học phí."); setModal(null); setActive(null); planForm.resetFields(); void load(); }
    catch (reason) { message.error(toMessage(reason)); }
  };
  const openInvoice = async (row: TuitionRow) => {
    if (!site) return;
    const receiptId = window.prompt("Nhập mã phiếu thu để xem hóa đơn:");
    if (!receiptId?.trim()) return;
    try { const invoice = await academicsApi.invoice(row.tuition_id, receiptId.trim(), site); Modal.info({ title: "Hóa đơn", width: 680, content: <pre style={{ whiteSpace: "pre-wrap", maxHeight: 420, overflow: "auto" }}>{JSON.stringify(invoice, null, 2)}</pre> }); }
    catch (reason) { message.error(toMessage(reason)); }
  };
  const sendReminder = async (row: TuitionRow) => {
    if (!site) return;
    try { const result = await academicsApi.sendTuitionReminders(row.class_id, site); message.success(`Đã gọi API nhắc học phí cho lớp ${row.class_name}. ${JSON.stringify(result)}`); }
    catch (reason) { message.error(toMessage(reason)); }
  };
  const columns = [
    { title: "Học viên", dataIndex: "student_name" }, { title: "Lớp", dataIndex: "class_name" }, { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Tổng học phí", dataIndex: "total_due", render: (v: number) => money(v) }, { title: "Đã thu", dataIndex: "amount_paid", render: (v: number) => money(v) }, { title: "Còn lại", dataIndex: "balance", render: (v: number) => money(v) },
    { title: "Trạng thái", dataIndex: "status", render: (v: string) => <Tag color={v === "da_dong" ? "green" : v === "dong_mot_phan" ? "gold" : "red"}>{v}</Tag> },
    { title: "Thao tác", render: (_: unknown, row: TuitionRow) => <Space wrap>{canCollect && <Button size="small" onClick={() => { setActive(row); setModal("receipt"); }}>Thu tiền</Button>}{canManagePlan && <Button size="small" onClick={() => { setActive(row); setModal("plan"); void academicsApi.installments(row.tuition_id, row.site_code).then((data) => planForm.setFieldsValue(data)).catch((e) => message.error(toMessage(e))); }}>Kế hoạch</Button>}<Button size="small" onClick={() => void openInvoice(row)}>Hóa đơn</Button>{canSendReminder && <Button size="small" onClick={() => void sendReminder(row)}>Nhắc học phí</Button>}</Space> },
  ];
  return <Card title={`Học phí · ${site || "Chưa chọn cơ sở"}`}>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    <Alert type="info" showIcon title="Mỗi lần thu ghi một phiếu tại CSDL của cơ sở. Có thể thu một phần nhiều lần và đổi phương thức giữa tiền mặt, chuyển khoản hoặc thẻ. Nếu API timeout, kiểm tra lại phiếu trước khi thử thu lần nữa." style={{ marginBottom: 16 }} />
    <Table rowKey="tuition_id" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 1100 }} />
    <Modal title={`Ghi nhận thanh toán${active ? ` · ${active.student_name}` : ""}`} open={modal === "receipt"} onCancel={() => setModal(null)} footer={null} destroyOnClose><Form form={receiptForm} layout="vertical" onFinish={collect}><Form.Item label="Còn phải đóng"><Input value={active ? money(active.balance) : ""} disabled /></Form.Item><Form.Item name="amount" label="Số tiền nhận (đồng)" rules={[{ required: true }]}><InputNumber min={1} max={active?.balance || undefined} precision={0} style={{ width: "100%" }} /></Form.Item><Form.Item name="payment_method" label="Phương thức" rules={[{ required: true }]}><Select options={[{ value: "tien_mat", label: "Tiền mặt" }, { value: "chuyen_khoan", label: "Chuyển khoản" }, { value: "the", label: "Thẻ" }]} /></Form.Item><Form.Item name="note" label="Ghi chú"><Input maxLength={500} /></Form.Item><Button type="primary" htmlType="submit" block>Ghi phiếu thu</Button></Form></Modal>
    <Modal title="Kế hoạch học phí" open={modal === "plan"} onCancel={() => setModal(null)} footer={null} destroyOnClose><Form form={planForm} layout="vertical" onFinish={savePlan}><Form.Item name="payment_mode" label="Cách đóng" rules={[{ required: true }]}><Select options={[{ value: "full", label: "Đóng một lần" }, { value: "monthly", label: "Chia theo tháng" }]} /></Form.Item><Form.Item noStyle shouldUpdate>{({ getFieldValue }) => getFieldValue("payment_mode") === "monthly" ? <Form.Item name="installment_count" label="Số tháng" rules={[{ required: true }]}><Select options={[3, 6, 9, 12].map((n) => ({ value: n, label: `${n} tháng` }))} /></Form.Item> : null}</Form.Item><Form.Item name="first_due_date" label="Ngày đến hạn đầu tiên" rules={[{ required: true }]}><Input type="date" min={new Date().toLocaleDateString("en-CA")} /></Form.Item><Button type="primary" htmlType="submit" block>Lưu kế hoạch</Button></Form></Modal>
  </Card>;
}

function money(value: number) { return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(value || 0); }
function toMessage(error: unknown) { return error instanceof Error ? error.message : "Yêu cầu API thất bại."; }
