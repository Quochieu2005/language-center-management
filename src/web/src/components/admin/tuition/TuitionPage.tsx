"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Col, Form, Input, InputNumber, Modal, Row, Select, Space, Statistic, Table, Tag, message } from "antd";
import { academicsApi, type TuitionReceipt, type TuitionRow } from "@/lib/api/academics";
import { adminApi, type TuitionFinancialReport } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { ALL_SITES, useSiteScope } from "@/lib/auth/site-scope";

type RefundValues = { receipt_id: string; amount: number; payment_method: "tien_mat" | "chuyen_khoan" | "the"; reason: string };
type RefundAttempt = { signature: string; idempotencyKey: string; values: RefundValues };
type TuitionStatusFilter = "all" | "con_no" | "chua_dong" | "dong_mot_phan" | "da_dong" | "hoan_tien";
const tuitionPageSize = 20;

export default function TuitionPage() {
  const { user } = useSession();
  const { selectedSite } = useSiteScope();
  const site = user?.role === "admin_big" ? selectedSite : user?.site_code || null;
  const canCollect = user?.role === "ke_toan";
  const canRefund = canCollect;
  const canManagePlan = ["admin_big", "admin_small", "ke_toan"].includes(user?.role || "");
  const canSendReminder = canManagePlan;
  const [rows, setRows] = useState<TuitionRow[]>([]);
  const [active, setActive] = useState<TuitionRow | null>(null);
  const [modal, setModal] = useState<"receipt" | "plan" | "refund" | null>(null);
  const [refundReceipts, setRefundReceipts] = useState<TuitionReceipt[]>([]);
  const [refundReceiptId, setRefundReceiptId] = useState("");
  const refundAttempts = useRef<Record<string, RefundAttempt>>({});
  const [refundLoading, setRefundLoading] = useState(false);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<TuitionFinancialReport | null>(null);
  const [summaryError, setSummaryError] = useState("");
  const [statusFilter, setStatusFilter] = useState<TuitionStatusFilter>("con_no");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const [partial, setPartial] = useState<string[]>([]);
  const [receiptForm] = Form.useForm();
  const [planForm] = Form.useForm();
  const [refundForm] = Form.useForm();
  const load = useCallback(async () => {
    if (!site) { setRows([]); setCount(0); setLoading(false); return; }
    setLoading(true);
    try {
      const result = await academicsApi.tuition(site === ALL_SITES ? undefined : site, {
        status: statusFilter === "all" ? undefined : statusFilter,
        search: search || undefined, limit: tuitionPageSize, offset,
      });
      setRows(result.results);
      setCount(result.count || 0);
      setPartial(result.missing_sites || []);
      setError("");
    }
    catch (reason) { setRows([]); setCount(0); setError(toMessage(reason)); setPartial([]); }
    finally { setLoading(false); }
  }, [site, statusFilter, search, offset]);
  const loadSummary = useCallback(async () => {
    if (!site) { setSummary(null); return; }
    try {
      setSummary(await adminApi.tuitionFinancialSummary(site === ALL_SITES ? undefined : site));
      setSummaryError("");
    } catch (reason) { setSummary(null); setSummaryError(toMessage(reason)); }
  }, [site]);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) { void load(); void loadSummary(); } }); return () => { cancelled = true; }; }, [load, loadSummary]);
  const collect = async (values: { amount: number; payment_method: "tien_mat" | "chuyen_khoan" | "the"; note?: string }) => {
    if (!site || !active) return;
    try {
      const key = crypto.randomUUID().replaceAll("-", "").slice(0, 24);
      const result = await academicsApi.collectTuition(active.tuition_id, active.site_code, { ...values, idempotency_key: key });
      const email = result.invoice_email && typeof result.invoice_email === "object" ? String((result.invoice_email as Record<string, unknown>).status || "") : "";
      message.success(email === "sent" || email === "already_sent" ? "Đã ghi nhận khoản thu và gửi hóa đơn qua email." : "Đã ghi nhận khoản thu. Trạng thái gửi email được API trả về; kiểm tra dữ liệu trước khi thu lại.");
      setModal(null); setActive(null); receiptForm.resetFields(); void load(); void loadSummary();
    } catch (reason) { message.error(`${toMessage(reason)} Nếu kết quả không rõ, tải lại danh sách/tra cứu phiếu trước khi gửi khoản thu mới.`); }
  };
  const savePlan = async (values: { payment_mode: "full" | "monthly"; installment_count?: 3 | 6 | 9 | 12; first_due_date: string }) => {
    if (!site || !active) return;
    try { await academicsApi.saveInstallments(active.tuition_id, active.site_code, values); message.success("Đã lưu kế hoạch đóng học phí."); setModal(null); setActive(null); planForm.resetFields(); void load(); }
    catch (reason) { message.error(toMessage(reason)); }
  };
  const openRefund = async (row: TuitionRow) => {
    setActive(row);
    setModal("refund");
    setRefundLoading(true);
    try {
      const result = await academicsApi.tuitionReceipts(row.tuition_id, row.site_code);
      const receipts = result.results.filter((receipt) => receipt.type === "thu");
      const refundable = receipts.filter((receipt) => receipt.refundable_amount > 0);
      setRefundReceipts(receipts);
      const pending = refundAttempts.current[row.tuition_id];
      if (pending) {
        setRefundReceiptId(pending.values.receipt_id);
        refundForm.setFieldsValue(pending.values);
        if (!refundable.length) message.info("Không còn số tiền để hoàn mới. Có thể gửi lại biểu mẫu để xác nhận kết quả lần trước.");
        return;
      }
      if (!refundable.length) {
        message.info("Khoản học phí này không còn số tiền có thể hoàn.");
        setModal(null);
        return;
      }
      const receipt = refundable[0];
      setRefundReceiptId(receipt.receipt_id);
      refundForm.resetFields();
      refundForm.setFieldsValue({ receipt_id: receipt.receipt_id, amount: receipt.refundable_amount, payment_method: receipt.payment_method });
    } catch (reason) {
      message.error(toMessage(reason));
      setModal(null);
    } finally { setRefundLoading(false); }
  };
  const refund = async (values: RefundValues) => {
    if (!active) return;
    const signature = JSON.stringify([values.receipt_id, values.amount, values.payment_method, values.reason]);
    const previous = refundAttempts.current[active.tuition_id];
    const attempt = previous?.signature === signature ? previous : {
      signature, idempotencyKey: crypto.randomUUID(), values,
    };
    refundAttempts.current[active.tuition_id] = attempt;
    setRefundSubmitting(true);
    try {
      await academicsApi.refundTuition(active.tuition_id, values.receipt_id, active.site_code, { ...values, idempotency_key: attempt.idempotencyKey });
      message.success("Đã ghi nhận phiếu hoàn và cập nhật công nợ.");
      delete refundAttempts.current[active.tuition_id];
      setModal(null); setActive(null); setRefundReceiptId(""); refundForm.resetFields(); void load(); void loadSummary();
    } catch (reason) {
      message.error(`${toMessage(reason)} Nếu kết quả không rõ, gửi lại cùng biểu mẫu để API trả đúng phiếu đã ghi.`);
    } finally { setRefundSubmitting(false); }
  };
  const openInvoice = async (row: TuitionRow) => {
    if (!site) return;
    const receiptId = window.prompt("Nhập mã phiếu thu để xem hóa đơn:");
    if (!receiptId?.trim()) return;
    try { const invoice = await academicsApi.invoice(row.tuition_id, receiptId.trim(), row.site_code); Modal.info({ title: "Hóa đơn", width: 680, content: <pre style={{ whiteSpace: "pre-wrap", maxHeight: 420, overflow: "auto" }}>{JSON.stringify(invoice, null, 2)}</pre> }); }
    catch (reason) { message.error(toMessage(reason)); }
  };
  const sendReminder = async (row: TuitionRow) => {
    if (!site) return;
    try { const result = await academicsApi.sendTuitionReminders(row.class_id, row.site_code); message.success(`Đã gọi API nhắc học phí cho lớp ${row.class_name}. ${JSON.stringify(result)}`); }
    catch (reason) { message.error(toMessage(reason)); }
  };
  const columns = [
    { title: "Học viên", dataIndex: "student_name" }, { title: "Lớp", dataIndex: "class_name" }, { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Tổng học phí", dataIndex: "total_due", render: (v: number) => money(v) }, { title: "Đã thu", dataIndex: "amount_paid", render: (v: number) => money(v) }, { title: "Còn lại", dataIndex: "balance", render: (v: number) => money(v) },
    { title: "Trạng thái", dataIndex: "status", render: (v: string) => <Tag color={v === "da_dong" ? "green" : v === "dong_mot_phan" ? "gold" : "red"}>{v}</Tag> },
    { title: "Thao tác", render: (_: unknown, row: TuitionRow) => <Space wrap>{canCollect && <Button size="small" onClick={() => { setActive(row); setModal("receipt"); }}>Thu tiền</Button>}{canRefund && row.amount_paid > 0 && <Button size="small" danger disabled={refundLoading || refundSubmitting} onClick={() => void openRefund(row)}>Hoàn tiền</Button>}{canManagePlan && <Button size="small" onClick={() => { setActive(row); setModal("plan"); void academicsApi.installments(row.tuition_id, row.site_code).then((data) => planForm.setFieldsValue(data)).catch((e) => message.error(toMessage(e))); }}>Kế hoạch</Button>}<Button size="small" onClick={() => void openInvoice(row)}>Hóa đơn</Button>{canSendReminder && <Button size="small" onClick={() => void sendReminder(row)}>Nhắc học phí</Button>}</Space> },
  ];
  return <Card title={`Học phí · ${site === ALL_SITES ? "Toàn hệ thống" : site || "Chưa chọn cơ sở"}`} extra={<Button onClick={() => { void load(); void loadSummary(); }}>Tải lại</Button>}>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    {partial.length > 0 && <Alert type="warning" showIcon title={`Global Query thiếu site: ${partial.join(", ")}; dữ liệu chưa đầy đủ.`} style={{ marginBottom: 16 }} />}
    {summaryError && <Alert type="warning" showIcon title={`Chưa tải được tổng công nợ: ${summaryError}`} style={{ marginBottom: 16 }} />}
    {summary && !summary.complete && <Alert type="warning" showIcon title={`Báo cáo công nợ thiếu site: ${summary.missing_sites.join(", ")}; tổng bên dưới chưa đầy đủ.`} style={{ marginBottom: 16 }} />}
    <Alert type="info" showIcon title="Mỗi lần thu ghi một phiếu tại CSDL của cơ sở. Có thể thu một phần nhiều lần và đổi phương thức giữa tiền mặt, chuyển khoản hoặc thẻ. Nếu API timeout, kiểm tra lại phiếu trước khi thử thu lần nữa." style={{ marginBottom: 16 }} />
    <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
      <Col xs={24} sm={12} xl={6}><Statistic title="Tổng còn nợ" value={summary ? summary.totals.outstanding : "—"} formatter={(value) => typeof value === "number" ? money(value) : value} /></Col>
      <Col xs={24} sm={12} xl={6}><Statistic title="Khoản còn nợ" value={summary ? summary.totals.accounts_with_balance : "—"} /></Col>
      <Col xs={24} sm={12} xl={6}><Statistic title="Tổng đã thu ròng" value={summary ? summary.totals.net_collected : "—"} formatter={(value) => typeof value === "number" ? money(value) : value} /></Col>
      <Col xs={24} sm={12} xl={6}><Statistic title="Số khoản học phí" value={summary ? summary.totals.tuition_accounts : "—"} /></Col>
    </Row>
    <Space wrap style={{ marginBottom: 16 }}>
      <Select value={statusFilter} onChange={(value: TuitionStatusFilter) => { setStatusFilter(value); setOffset(0); }} options={[
        { value: "con_no", label: "Còn nợ" }, { value: "all", label: "Tất cả khoản học phí" },
        { value: "chua_dong", label: "Chưa đóng" }, { value: "dong_mot_phan", label: "Đóng một phần" },
        { value: "da_dong", label: "Đã đóng đủ" }, { value: "hoan_tien", label: "Đã hoàn tiền" },
      ]} style={{ minWidth: 210 }} />
      <Input.Search placeholder="Tìm học viên hoặc lớp" allowClear value={searchInput} onChange={(event) => {
        setSearchInput(event.target.value);
        if (!event.target.value) { setSearch(""); setOffset(0); }
      }} onSearch={(value) => { setSearch(value.trim()); setOffset(0); }} style={{ width: 320 }} />
    </Space>
    <Table rowKey="tuition_id" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 1100 }} locale={{ emptyText: count !== 0 ? undefined : error ? "Không tải được danh sách học phí." : summaryError ? "Chưa xác định được công nợ; hãy tải lại." : summary?.totals.tuition_accounts === 0 ? "Chưa có khoản học phí. Khoản phí phát sinh khi học viên được đăng ký vào lớp." : statusFilter === "con_no" && !search ? "Hiện không có khoản học phí còn nợ." : "Không có khoản học phí phù hợp với bộ lọc." }} pagination={{ current: Math.floor(offset / tuitionPageSize) + 1, pageSize: tuitionPageSize, total: count, showSizeChanger: false, showTotal: (total) => `${total} khoản học phí`, onChange: (page) => setOffset((page - 1) * tuitionPageSize) }} />
    <Modal title={`Ghi nhận thanh toán${active ? ` · ${active.student_name}` : ""}`} open={modal === "receipt"} onCancel={() => setModal(null)} footer={null} destroyOnHidden><Form form={receiptForm} layout="vertical" onFinish={collect}><Form.Item label="Còn phải đóng"><Input value={active ? money(active.balance) : ""} disabled /></Form.Item><Form.Item name="amount" label="Số tiền nhận (đồng)" rules={[{ required: true }]}><InputNumber min={1} max={active?.balance || undefined} precision={0} style={{ width: "100%" }} /></Form.Item><Form.Item name="payment_method" label="Phương thức" rules={[{ required: true }]}><Select options={[{ value: "tien_mat", label: "Tiền mặt" }, { value: "chuyen_khoan", label: "Chuyển khoản" }, { value: "the", label: "Thẻ" }]} /></Form.Item><Form.Item name="note" label="Ghi chú"><Input maxLength={500} /></Form.Item><Button type="primary" htmlType="submit" block>Ghi phiếu thu</Button></Form></Modal>
    <Modal title="Kế hoạch học phí" open={modal === "plan"} onCancel={() => setModal(null)} footer={null} destroyOnHidden><Form form={planForm} layout="vertical" onFinish={savePlan}><Form.Item name="payment_mode" label="Cách đóng" rules={[{ required: true }]}><Select options={[{ value: "full", label: "Đóng một lần" }, { value: "monthly", label: "Chia theo tháng" }]} /></Form.Item><Form.Item noStyle shouldUpdate>{({ getFieldValue }) => getFieldValue("payment_mode") === "monthly" ? <Form.Item name="installment_count" label="Số tháng" rules={[{ required: true }]}><Select options={[3, 6, 9, 12].map((n) => ({ value: n, label: `${n} tháng` }))} /></Form.Item> : null}</Form.Item><Form.Item name="first_due_date" label="Ngày đến hạn đầu tiên" rules={[{ required: true }]}><Input type="date" min={new Date().toLocaleDateString("en-CA")} /></Form.Item><Button type="primary" htmlType="submit" block>Lưu kế hoạch</Button></Form></Modal>
    <Modal title={`Hoàn học phí${active ? ` · ${active.student_name}` : ""}`} open={modal === "refund"} onCancel={() => { if (!refundSubmitting) setModal(null); }} closable={!refundSubmitting} maskClosable={!refundSubmitting} footer={null} destroyOnHidden>
      <Form form={refundForm} layout="vertical" onFinish={refund}>
        <Form.Item name="receipt_id" label="Phiếu thu gốc" rules={[{ required: true }]}>
          <Select loading={refundLoading} onChange={(id) => { setRefundReceiptId(id); const receipt = refundReceipts.find((item) => item.receipt_id === id); if (receipt) refundForm.setFieldValue("amount", receipt.refundable_amount); }} options={refundReceipts.filter((receipt) => receipt.refundable_amount > 0 || receipt.receipt_id === refundReceiptId).map((receipt) => ({ value: receipt.receipt_id, label: `${receipt.receipt_id} · còn hoàn ${money(receipt.refundable_amount)}` }))} />
        </Form.Item>
        <Form.Item label="Số tiền còn có thể hoàn"><Input value={money(refundReceipts.find((receipt) => receipt.receipt_id === refundReceiptId)?.refundable_amount || 0)} disabled /></Form.Item>
        <Form.Item name="amount" label="Số tiền hoàn (đồng)" rules={[{ required: true }]}><InputNumber min={1} max={refundReceipts.find((receipt) => receipt.receipt_id === refundReceiptId)?.refundable_amount || undefined} precision={0} style={{ width: "100%" }} /></Form.Item>
        <Form.Item name="payment_method" label="Phương thức hoàn" rules={[{ required: true }]}><Select options={[{ value: "tien_mat", label: "Tiền mặt" }, { value: "chuyen_khoan", label: "Chuyển khoản" }, { value: "the", label: "Thẻ" }]} /></Form.Item>
        <Form.Item name="reason" label="Lý do hoàn" rules={[{ required: true, whitespace: true }]}><Input maxLength={500} /></Form.Item>
        <Button type="primary" danger htmlType="submit" block loading={refundSubmitting} disabled={refundLoading}>Ghi phiếu hoàn</Button>
      </Form>
    </Modal>
  </Card>;
}

function money(value: number) { return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(value || 0); }
function toMessage(error: unknown) { return error instanceof Error ? error.message : "Yêu cầu API thất bại."; }
