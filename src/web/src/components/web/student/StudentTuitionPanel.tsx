"use client";

import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Empty, InputNumber, Modal, Space, Spin, Tag, Typography, message } from "antd";
import { academicsApi, type ApiRow, type StudentSePayPayment } from "@/lib/api/academics";
import styles from "./StudentTuitionPanel.module.scss";

type Installment = { installment_id: string; sequence: number; amount_due: number | string; amount_paid: number | string; balance: number | string; status: string };
type Tuition = ApiRow & {
  tuition_id: string; course_name: string; amount_due: number | string;
  amount_paid: number | string; balance: number | string; installments?: Installment[];
  active_payment?: { attempt_id: string } | null;
};

const money = (value: number | string) => `${Number(value || 0).toLocaleString("vi-VN")} ₫`;

export function StudentTuitionPanel({ rows, loading, slug, onRefresh }: {
  rows: ApiRow[]; loading: boolean; slug: string; onRefresh: () => Promise<void>;
}) {
  const [selected, setSelected] = useState<{ tuition: Tuition; installment: Installment } | null>(null);
  const [payment, setPayment] = useState<StudentSePayPayment | null>(null);
  const [amount, setAmount] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const keyRef = useRef<string | null>(null);
  const refreshedRef = useRef<string | null>(null);

  const begin = (tuition: Tuition, installment: Installment) => {
    keyRef.current = null;
    setSelected({ tuition, installment });
    setAmount(Number(installment.balance));
    setPayment(null);
    setOpen(true);
  };

  const createPayment = async () => {
    if (!selected || !slug || !amount || amount < 1) return;
    setBusy(true);
    keyRef.current ||= crypto.randomUUID();
    try {
      const result = await academicsApi.createStudentSePayPayment(
        slug, selected.tuition.tuition_id,
        { installment_id: selected.installment.installment_id, amount }, keyRef.current,
      );
      keyRef.current = null;
      setPayment(result);
      message.success("Đã tạo yêu cầu thanh toán. Quét QR và chờ xác nhận.");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Không tạo được yêu cầu thanh toán.");
    } finally {
      setBusy(false);
    }
  };

  const resumePayment = async (tuition: Tuition) => {
    if (!tuition.active_payment?.attempt_id) return;
    setBusy(true);
    setSelected({ tuition, installment: tuition.installments?.find((item) => Number(item.balance) > 0) || {
      installment_id: "", sequence: 1, amount_due: 0, amount_paid: 0, balance: 0, status: "chua_dong",
    } });
    setPayment(null);
    setOpen(true);
    try {
      const current = await academicsApi.studentPaymentStatus(slug, tuition.active_payment.attempt_id);
      setPayment(current);
      if (current.status === "da_thanh_toan") void onRefresh();
    } catch (error) {
      setOpen(false);
      message.error(error instanceof Error ? error.message : "Không tải được trạng thái thanh toán.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!open || !payment || payment.status !== "cho_thanh_toan") return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await academicsApi.studentPaymentStatus(slug, payment.attempt_id);
        if (stopped) return;
        setPayment(next);
        if (next.status === "da_thanh_toan" && refreshedRef.current !== next.attempt_id) {
          refreshedRef.current = next.attempt_id;
          void onRefresh();
        }
        if (next.status === "cho_thanh_toan") timer = setTimeout(poll, 3000);
      } catch {
        if (!stopped) timer = setTimeout(poll, 5000);
      }
    };
    timer = setTimeout(poll, 3000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [open, payment, slug, onRefresh]);

  const items = rows as Tuition[];
  if (loading && items.length === 0) return <div className={styles.loading}><Spin description="Đang tải học phí..." /></div>;
  if (items.length === 0) return <Empty description="Chưa có khoản học phí." />;

  return <>
    <div className={styles.list}>
      {items.map((tuition) => {
        const installments = tuition.installments || [];
        const firstUnpaid = installments.find((item) => Number(item.balance) > 0);
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
              <span>Kỳ {item.sequence}</span><span>{money(item.amount_paid)} / {money(item.amount_due)}</span>
              <Tag>{money(item.balance)} còn nợ</Tag>
            </div>)}
          </div>}
          {balance > 0 && <Button type="primary" loading={busy} onClick={() => tuition.active_payment
            ? void resumePayment(tuition)
            : firstUnpaid && begin(tuition, firstUnpaid)}>
            {tuition.active_payment ? "Tiếp tục thanh toán" : "Thanh toán qua SePay"}
          </Button>}
        </Card>;
      })}
    </div>

    <Modal title={payment ? "Thanh toán học phí" : "Nhập số tiền muốn thanh toán"} open={open}
      onCancel={() => setOpen(false)} footer={null} destroyOnHidden>
      {busy && !payment ? <Spin description="Đang tải yêu cầu..." /> : payment ? <Space orientation="vertical" size="middle" className={styles.paymentDetails}>
        {payment.status === "da_thanh_toan" ? <Alert type="success" showIcon title="Đã nhận thanh toán" description="Học phí đã được cập nhật. Biên nhận sẽ được gửi tới email học viên." />
          : payment.status === "cho_thanh_toan" ? <Alert type="info" showIcon title="Đang chờ ngân hàng xác nhận" description="Sau khi chuyển khoản, giữ cửa sổ này mở hoặc quay lại để kiểm tra trạng thái." />
            : <Alert type="warning" showIcon title={payment.status === "can_doi_soat" ? "Giao dịch cần đối soát" : "Yêu cầu không còn hiệu lực"} description="Không chuyển lại theo mã QR này. Liên hệ cơ sở để kiểm tra giao dịch." />}
        {payment.status === "cho_thanh_toan" && <img className={styles.qr} src={payment.qr_url} alt="Mã QR thanh toán học phí" />}
        <div className={styles.bankInfo}>
          <div><span>Số tiền</span><b>{money(payment.amount)}</b></div>
          <div><span>Ngân hàng</span><b>{payment.bank_code}</b></div>
          <div><span>Số tài khoản</span><b>{payment.bank_account}</b></div>
          <div><span>Nội dung chuyển khoản</span><b>{payment.payment_code}</b></div>
          <div><span>Hạn thanh toán</span><b>{new Date(payment.expires_at).toLocaleString("vi-VN", { hour12: false, timeZone: "Asia/Ho_Chi_Minh" })}</b></div>
        </div>
        {payment.status === "da_thanh_toan" && <Button onClick={() => setOpen(false)}>Hoàn tất</Button>}
      </Space> : selected && <Space orientation="vertical" className={styles.paymentDetails}>
        <Typography.Paragraph type="secondary">Kỳ {selected.installment.sequence}, còn phải đóng {money(selected.installment.balance)}. Bạn có thể thanh toán một phần.</Typography.Paragraph>
        <InputNumber min={1} max={Math.min(Number(selected.installment.balance), Number(selected.tuition.balance))}
          value={amount} onChange={setAmount} precision={0} addonAfter="₫" style={{ width: "100%" }} />
        <Button type="primary" block loading={busy} disabled={!amount || amount < 1}
          onClick={() => void createPayment()}>Tạo mã QR</Button>
      </Space>}
    </Modal>
  </>;
}
