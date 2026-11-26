"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Avatar, Button, Form, Input, Select } from "antd";
import { UserOutlined } from "@ant-design/icons";
import { SelfAvatarUploader } from "@/components/shared/SelfAvatarUploader";
import { academicsApi, type ApiRow } from "@/lib/api/academics";
import styles from "./AccountProfile.module.scss";

export type ProfileValues = {
  full_name: string;
  birth_date?: string | null;
  gender?: string | null;
  phone?: string | null;
  address?: string | null;
};

type Props = {
  profile: ApiRow;
  slug: string;
  saving?: boolean;
  /** Resolves with an error message, or null when saved. */
  onSave: (values: ProfileValues) => Promise<string | null>;
  onAvatarUploaded?: (url: string | null) => void;
};

const text = (value: unknown) => (typeof value === "string" ? value : "");

export default function AccountProfile({ profile, slug, saving = false, onSave, onAvatarUploaded }: Props) {
  const [form] = Form.useForm<ProfileValues>();
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [avatar, setAvatar] = useState<string | null>(typeof profile.avatar_secure_url === "string" ? profile.avatar_secure_url : null);
  const fullName = text(profile.full_name);

  useEffect(() => {
    form.setFieldsValue({
      full_name: fullName, birth_date: text(profile.birth_date), gender: text(profile.gender) || undefined,
      phone: text(profile.phone), address: text(profile.address),
    });
  }, [form, fullName, profile.birth_date, profile.gender, profile.phone, profile.address]);

  const submit = async (values: ProfileValues) => {
    setError("");
    setSaved(false);
    const failure = await onSave({
      full_name: values.full_name.trim(), birth_date: values.birth_date || null, gender: values.gender || null,
      phone: values.phone?.trim() || null, address: values.address?.trim() || null,
    });
    if (failure) setError(failure);
    else setSaved(true);
  };

  return <div className={styles.layout}>
    <aside className={styles.side}>
      <Avatar className={styles.avatar} size={112} src={avatar || undefined} icon={<UserOutlined />} alt="Ảnh đại diện" />
      <h2>{fullName || "Hồ sơ của bạn"}</h2>
      <p className={styles.email}>{text(profile.email)}</p>
      <div className={styles.uploader}>
        <SelfAvatarUploader
          slug={slug}
          hasAvatar={Boolean(avatar)}
          api={{ createIntent: academicsApi.createStudentSelfAvatarIntent, complete: academicsApi.completeStudentSelfAvatar }}
          onUploaded={(url) => { setAvatar(url); onAvatarUploaded?.(url); }}
        />
        <small>JPG, PNG hoặc WebP · tối đa 5 MB</small>
      </div>
      <nav className={styles.links} aria-label="Lối tắt tài khoản">
        <Link href="/courses">Xem khóa học <span aria-hidden="true">→</span></Link>
        <Link href="/student">Cổng học viên <span aria-hidden="true">→</span></Link>
        <Link href="/password/change">Đổi mật khẩu <span aria-hidden="true">→</span></Link>
      </nav>
    </aside>

    <section className={styles.card} aria-labelledby="account-form-title">
      <p className={styles.eyebrow}>THÔNG TIN CÁ NHÂN</p>
      <h2 id="account-form-title">Cập nhật hồ sơ</h2>
      <p className={styles.note}>Email do hệ thống cấp nên không đổi được ở đây. Các thông tin còn lại bạn có thể sửa bất cứ lúc nào.</p>
      {error && <Alert className={styles.alert} type="error" showIcon title={error} />}
      {saved && <Alert className={styles.alert} type="success" showIcon title="Đã lưu hồ sơ của bạn." />}
      <Form form={form} layout="vertical" requiredMark={false} onFinish={submit} onValuesChange={() => setSaved(false)} disabled={saving}>
        <div className={styles.grid}>
          <Form.Item className={styles.wide} name="full_name" label="Họ và tên" rules={[{ required: true, whitespace: true, message: "Nhập họ tên." }, { max: 150 }]}>
            <Input size="large" maxLength={150} autoComplete="name" />
          </Form.Item>
          <Form.Item label="Email"><Input size="large" value={text(profile.email)} disabled /></Form.Item>
          <Form.Item label="Mã hồ sơ"><Input size="large" value={text(profile.student_id)} disabled /></Form.Item>
          <Form.Item name="birth_date" label="Ngày sinh"><Input size="large" type="date" max={new Date().toISOString().slice(0, 10)} /></Form.Item>
          <Form.Item name="gender" label="Giới tính">
            <Select size="large" allowClear placeholder="Chọn giới tính" options={["Nam", "Nữ", "Khác"].map((value) => ({ value, label: value }))} />
          </Form.Item>
          <Form.Item name="phone" label="Số điện thoại" rules={[{ max: 20 }, { pattern: /^[+0-9().\s-]{6,20}$|^$/, message: "Số điện thoại không hợp lệ." }]}>
            <Input size="large" maxLength={20} autoComplete="tel" />
          </Form.Item>
          <Form.Item name="address" label="Địa chỉ" rules={[{ max: 300 }]}><Input size="large" maxLength={300} autoComplete="street-address" /></Form.Item>
        </div>
        <Button type="primary" htmlType="submit" size="large" loading={saving} className={styles.submit}>Lưu hồ sơ</Button>
      </Form>
    </section>
  </div>;
}
