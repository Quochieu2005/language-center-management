"use client";

import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Empty, Modal, Radio, Space, Spin, Tag, Typography, message } from "antd";
import { academicsApi, type ApiRow, type SePayCheckout, type StudentSePayPayment } from "@/lib/api/academics";
import { formatVnd as money, tuitionPaymentOptions, type PaymentOptionKey } from "@/lib/tuitionPaymentOptions";
import styles from "./StudentTuitionPanel.module.scss";

type Installment = { installment_id: string; sequence: number; amount_due: number | string; amount_paid: number | string; balance: number | string; status: string; due_date?: string };
type Tuition = ApiRow & {
  tuition_id: string; course_name: string; amount_due: number | string;
  amount_paid: number | string; balance: number | string; installments?: Installment[];
  active_payment?: { attempt_id: string } | null;
};

const CONFIRM_POLL_MS = 4000;
const CONFIRM_MAX_TRIES = 30;

/** Hand the signed fields to SePay's hosted checkout; card/bank details never touch our servers. */
function submitCheckout(checkout: SePayCheckout) {
  const form = document.createElement("form");
  form.method = checkout.method || "POST";
  form.action = checkout.action;
  Object.entries(checkout.fields).forEach(([name, value]) => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  });
  document.body.appendChild(form);
  form.submit();
}

export function StudentTuitionPanel({ rows, loading, slug, onRefresh, returnAttemptId, onReturnHandled }: {
  rows: ApiRow[]; loading: boolean; slug: string; onRefresh: () => Promise<void>;
  returnAttemptId?: string | null; onReturnHandled?: () => void;
}) {
  const [selected, setSelected] = useState<Tuition | null>(null);
  const [option, setOption] = useState<PaymentOptionKey>("next_installment");
  const [payment, setPayment] = useState<StudentSePayPayment | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const keyRef = useRef<{ scope: string; key: string } | null>(null);

  const startCheckout = (result: StudentSePayPayment) => {
    if (result.status === "cho_thanh_toan" && result.checkout) {
      message.loading("Đang chuyển sang trang thanh toán SePay...", 0);
      submitCheckout(result.checkout);
      return;
    }
    setPayment(result);
  };

  const pay = async () => {
    if (!selected || !slug) return;
    const scope = `${selected.tuition_id}:${option}`;
    // Keep one key per tuition+option so a lost response replays instead of creating a second attempt.
    if (keyRef.current?.scope !== scope) keyRef.current = { scope, key: crypto.randomUUID() };
    setBusy(true);
    try {
      const result = await academicsApi.createStudentSePayPayment(slug, selected.tuition_id, { option }, keyRef.current.key);
      startCheckout(result);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Không tạo được yêu cầu thanh toán.");
    } finally {
      setBusy(false);
    }
  };

  const resume = async (tuition: Tuition) => {
    if (!tuition.active_payment?.attempt_id) return;
    setBusy(true);
    try {
      const current = await academicsApi.studentPaymentStatus(slug, tuition.active_payment.attempt_id);
      if (current.status === "da_thanh_toan") {
        message.success("Khoản thanh toán trước đã được ghi nhận.");
        void onRefresh();
      } else {
        startCheckout(current);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Không tải được trạng thái thanh toán.");
    } finally {
      setBusy(false);
    }
  };

  // Back from SePay: the redirect proves nothing, so confirm through the API (IPN or order lookup).
  useEffect(() => {
    if (!returnAttemptId || !slug) return;
    let stopped = false;
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;
    queueMicrotask(() => { if (!stopped) setConfirming(true); });
    const check = async () => {
      tries += 1;
      try {
        const next = await academicsApi.studentPaymentStatus(slug, returnAttemptId);
        if (stopped) return;
        setPayment(next);
        if (next.status === "da_thanh_toan") { void onRefresh(); onReturnHandled?.(); return; }
        if (next.status !== "cho_thanh_toan" || tries >= CONFIRM_MAX_TRIES) { onReturnHandled?.(); return; }
      } catch {
        if (stopped || tries >= CONFIRM_MAX_TRIES) return;
      }
      timer = setTimeout(check, CONFIRM_POLL_MS);
    };
    void check();
    return () => { stopped = true; clearTimeout(timer); };
  }, [returnAttemptId, slug, onRefresh, onReturnHandled]);

  const items = rows as Tuition[];
  if (loading && items.length === 0) return <div className={styles.loading}><Spin description="Đang tải học phí..." /></div>;
  if (items.length === 0) return <Empty description="Chưa có khoản học phí." />;
  const options = selected ? tuitionPaymentOptions(Number(selected.balance), selected.installments) : [];

  return <>
    <div className={styles.list}>
      {items.map((tuition) => {
        const installments = tuition.installments || [];
        const balance = Number(tuition.balance || 0);
        return <Card key={tuition.tuition_id} className={styles.card}>
          <div className={styles.heading}>
            <div><Typography.Title level={5}>{tuition.course_name}</Typography.Title><Typography.Text type="secondary">Mã học phí: {tuition.tuition_id}</Typography.Text></div>
            <Tag color={balance > 0 ? "orange" : "green"}>{balance > 0 ? "Còn học phí" : "Đã thanh toán"}</Tag>
          </div>
          <div className={styles.amounts}>
            <span>Tổng: <b>{money(tuition.amount_due)}</b></span>
            <span>Đã đóng: <b>{money(tuition.amount_paid)}</b></span>
            <span>Còn lại: <b>{money(tuition.balance)}</b></span>
          </div>
          {installments.length > 0 && <div className={styles.installments}>
            {installments.map((item) => <div key={item.installment_id} className={styles.installment}>
              <span>Kỳ {item.sequence}{item.due_date ? ` · hạn ${new Date(item.due_date).toLocaleDateString("vi-VN")}` : ""}</span>
              <span>{money(item.amount_paid)} / {money(item.amount_due)}</span>
              <Tag color={Number(item.balance) > 0 ? (item.status === "qua_han" ? "red" : "default") : "green"}>
                {Number(item.balance) > 0 ? `${money(item.balance)} còn nợ` : "Đã đóng"}
              </Tag>
            </div>)}
          </div>}
          {balance > 0 && (tuition.active_payment
            ? <Button type="primary" loading={busy} onClick={() => void resume(tuition)}>Tiếp tục thanh toán</Button>
            : <Button type="primary" onClick={() => { setSelected(tuition); setOption("next_installment"); setPayment(null); }}>Thanh toán online</Button>)}
        </Card>;
      })}
    </div>

    <Modal title="Thanh toán học phí qua SePay" open={Boolean(selected) && !payment} onCancel={() => setSelected(null)} footer={null} destroyOnHidden>
      {selected && <Space orientation="vertical" size="middle" className={styles.paymentDetails}>
        <Typography.Text type="secondary">{selected.course_name} · còn nợ {money(selected.balance)}. Chọn số tiền muốn đóng lần này:</Typography.Text>
        <Radio.Group value={option} onChange={(event) => setOption(event.target.value)} style={{ width: "100%" }}>
          <Space orientation="vertical" style={{ width: "100%" }}>
            {options.map((item) => <Radio key={item.key} value={item.key}>
              <b>{item.label}: {money(item.amount)}</b> <Typography.Text type="secondary">· {item.hint}</Typography.Text>
            </Radio>)}
          </Space>
        </Radio.Group>
        <Alert type="info" showIcon title="Bạn sẽ được chuyển sang trang thanh toán của SePay (thẻ hoặc chuyển khoản). Hệ thống chỉ ghi nhận khi SePay xác nhận đã thu tiền." />
        <Button type="primary" block loading={busy} disabled={!options.length} onClick={() => void pay()}>Thanh toán qua SePay</Button>
      </Space>}
    </Modal>

    <Modal title="Kết quả thanh toán" open={Boolean(payment) || confirming} onCancel={() => { setPayment(null); setConfirming(false); }} footer={null} destroyOnHidden>
      {!payment ? <Spin description="Đang xác nhận giao dịch với SePay..." /> : <Space orientation="vertical" size="middle" className={styles.paymentDetails}>
        {payment.status === "da_thanh_toan" ? <Alert type="success" showIcon title="Đã nhận thanh toán" description="Học phí đã được cập nhật và trừ vào các kỳ. Biên nhận được gửi tới email của bạn." />
          : payment.status === "cho_thanh_toan" ? <Alert type="info" showIcon title="Chưa nhận được xác nhận từ SePay" description="Nếu bạn đã thanh toán, hệ thống sẽ tự cập nhật trong ít phút. Không thanh toán lại cho cùng khoản này." />
            : payment.status === "can_doi_soat" ? <Alert type="warning" showIcon title="Giao dịch cần đối soát" description="SePay đã báo thanh toán nhưng chưa khớp khoản học phí. Không thanh toán lại; cơ sở sẽ kiểm tra và liên hệ bạn." />
              : <Alert type="warning" showIcon title="Chưa thanh toán" description="Yêu cầu thanh toán đã hết hạn hoặc bị hủy và chưa có tiền được thu. Bạn có thể tạo yêu cầu mới." />}
        <div className={styles.bankInfo}>
          <div><span>Mã yêu cầu</span><b>{payment.attempt_id}</b></div>
          <div><span>Số tiền</span><b>{money(payment.amount)}</b></div>
          <div><span>Mã giao dịch SePay</span><b>{payment.payment_code}</b></div>
        </div>
        <Button onClick={() => { setPayment(null); setConfirming(false); }}>Đóng</Button>
      </Space>}
    </Modal>
  </>;
}
