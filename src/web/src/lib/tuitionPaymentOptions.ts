export type PaymentOptionKey = "next_installment" | "half" | "full";

type InstallmentLike = { amount_due: number | string; amount_paid: number | string; balance?: number | string; sequence?: number };

export type PaymentOption = { key: PaymentOptionKey; label: string; amount: number; hint: string };

/**
 * Mirrors core.academics.sepay.payment_options for display: the next unpaid installment,
 * half of the remaining balance (rounded up to whole VND) or the full balance.
 * The API recomputes the amount; these numbers only label the buttons.
 */
export function tuitionPaymentOptions(balance: number, installments: InstallmentLike[] = []): PaymentOption[] {
  const remaining = Math.max(0, Math.trunc(Number(balance) || 0));
  if (remaining <= 0) return [];
  const next = installments.find((item) => Number(item.amount_due) > Number(item.amount_paid));
  const nextAmount = next ? Math.min(remaining, Number(next.amount_due) - Number(next.amount_paid)) : remaining;
  const options: PaymentOption[] = [
    { key: "next_installment", label: next?.sequence ? `Kỳ ${next.sequence}` : "Kỳ tiếp theo", amount: nextAmount, hint: "Đóng hết kỳ chưa đóng gần nhất" },
    { key: "half", label: "Một nửa", amount: Math.ceil(remaining / 2), hint: "Một nửa số còn nợ, trừ dần vào các kỳ" },
    { key: "full", label: "Toàn bộ", amount: remaining, hint: "Tất toán toàn bộ học phí còn lại" },
  ];
  // Hide duplicates (e.g. one installment left): keep the first label for an amount.
  return options.filter((option, index) => options.findIndex((other) => other.amount === option.amount) === index);
}

export const formatVnd = (value: number | string) => `${Number(value || 0).toLocaleString("vi-VN")} ₫`;
