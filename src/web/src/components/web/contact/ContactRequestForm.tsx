"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api/client";
import { contactsApi, type ContactSite, type ContactSubmission } from "@/lib/api/contacts";
import styles from "./ContactRequestForm.module.scss";

const emptyForm: ContactSubmission = {
  site_code: "", full_name: "", email: "", phone: "", subject: "", message: "",
};

export default function ContactRequestForm() {
  const [sites, setSites] = useState<ContactSite[]>([]);
  const [missingSites, setMissingSites] = useState<string[]>([]);
  const [values, setValues] = useState(emptyForm);
  const [loadingSites, setLoadingSites] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const submission = useRef<{ signature: string; key: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    contactsApi.sites().then((result) => {
      if (cancelled) return;
      setSites(result.results);
      setMissingSites(result.missing_sites);
      setValues((current) => ({ ...current, site_code: current.site_code || result.results[0]?.site_code || "" }));
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : "Không tải được danh sách cơ sở.");
    }).finally(() => {
      if (!cancelled) setLoadingSites(false);
    });
    return () => { cancelled = true; };
  }, []);

  const update = (field: keyof ContactSubmission, value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
    setError("");
    setSuccess("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const body = { ...values, phone: values.phone?.trim() || "" };
    const signature = JSON.stringify(body);
    if (!submission.current || submission.current.signature !== signature) {
      submission.current = { signature, key: crypto.randomUUID() };
    }
    setSending(true);
    setError("");
    setSuccess("");
    try {
      const result = await contactsApi.submit(body, submission.current.key);
      const siteName = sites.find((site) => site.site_code === result.site_code)?.name || result.site_code;
      setSuccess(`Yêu cầu đã được gửi tới cơ sở ${siteName}. Trung tâm sẽ phản hồi qua email của bạn.`);
      setValues({ ...emptyForm, site_code: result.site_code });
      submission.current = null;
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Chưa gửi được yêu cầu. Vui lòng thử lại.");
    } finally {
      setSending(false);
    }
  };

  return (
    <section className={styles.section} aria-labelledby="contact-form-title">
      <div className={styles.heading}>
        <p className={styles.eyebrow}>GỬI YÊU CẦU</p>
        <h2 id="contact-form-title">Bạn muốn trao đổi điều gì?</h2>
        <p>Chọn cơ sở phụ trách. Quản trị viên sẽ xem nội dung và gửi phản hồi đến email bạn cung cấp.</p>
      </div>
      {missingSites.length > 0 && <p className={styles.warning} role="status">Một số cơ sở đang tạm thời không kết nối: {missingSites.join(", ")}. Các cơ sở còn khả dụng vẫn nhận yêu cầu.</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {success && <p className={styles.success} role="status">{success}</p>}
      <form className={styles.form} onSubmit={submit}>
        <div className={styles.grid}>
          <label className={styles.field}>
            <span>Họ tên <b aria-hidden="true">*</b></span>
            <input autoComplete="name" maxLength={120} required value={values.full_name} onChange={(event) => update("full_name", event.target.value)} />
          </label>
          <label className={styles.field}>
            <span>Email <b aria-hidden="true">*</b></span>
            <input autoComplete="email" maxLength={254} required type="email" value={values.email} onChange={(event) => update("email", event.target.value)} />
          </label>
          <label className={styles.field}>
            <span>Cơ sở muốn liên hệ <b aria-hidden="true">*</b></span>
            <select required disabled={loadingSites || sites.length === 0} value={values.site_code} onChange={(event) => update("site_code", event.target.value)}>
              <option value="" disabled>{loadingSites ? "Đang tải cơ sở…" : "Chọn cơ sở"}</option>
              {sites.map((site) => <option key={site.site_code} value={site.site_code}>{site.name} ({site.site_code})</option>)}
            </select>
          </label>
          <label className={styles.field}>
            <span>Số điện thoại <small>(không bắt buộc)</small></span>
            <input autoComplete="tel" maxLength={20} value={values.phone} onChange={(event) => update("phone", event.target.value)} />
          </label>
          <label className={`${styles.field} ${styles.full}`}>
            <span>Tiêu đề <b aria-hidden="true">*</b></span>
            <input maxLength={160} required value={values.subject} onChange={(event) => update("subject", event.target.value)} />
          </label>
          <label className={`${styles.field} ${styles.full}`}>
            <span>Nội dung <b aria-hidden="true">*</b></span>
            <textarea maxLength={5000} required rows={6} value={values.message} onChange={(event) => update("message", event.target.value)} />
          </label>
        </div>
        <div className={styles.actions}>
          <p>Thông tin này chỉ được dùng để tiếp nhận và phản hồi yêu cầu của bạn.</p>
          <button type="submit" disabled={sending || loadingSites || sites.length === 0}>
            {sending ? "Đang gửi…" : "Gửi yêu cầu"}
          </button>
        </div>
      </form>
    </section>
  );
}
