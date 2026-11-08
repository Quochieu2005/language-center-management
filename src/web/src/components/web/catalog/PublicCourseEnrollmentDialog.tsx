"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Form, Input, Modal, Select } from "antd";
import { ApiError } from "@/lib/api/client";
import {
  catalogApi,
  type PublicCourse,
  type PublicCourseClass,
  type PublicEnrollmentResult,
} from "@/lib/api/catalog";
import styles from "./PublicCourseCatalog.module.scss";

type EnrollmentValues = {
  site_code: string;
  class_id: string;
  full_name: string;
  email: string;
  phone?: string;
};

function dateLabel(value: string) {
  return value.split("-").reverse().join("/");
}

export default function PublicCourseEnrollmentDialog({
  course,
  onClose,
}: {
  course: PublicCourse | null;
  onClose: () => void;
}) {
  const [form] = Form.useForm<EnrollmentValues>();
  const [siteCode, setSiteCode] = useState(course?.branches[0]?.site_code ?? "");
  const [classResponse, setClassResponse] = useState<{
    key: string;
    results: PublicCourseClass[];
    error: string;
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PublicEnrollmentResult | null>(null);
  const courseSlug = course?.slug ?? "";
  const classRequestKey = courseSlug && siteCode ? `${courseSlug}:${siteCode}` : "";
  const currentClassResponse = classResponse?.key === classRequestKey ? classResponse : null;
  const classes = currentClassResponse?.results ?? [];
  const classError = currentClassResponse?.error ?? "";
  const loadingClasses = Boolean(classRequestKey && !currentClassResponse);

  useEffect(() => {
    if (!classRequestKey) return;
    let current = true;
    catalogApi.publicClasses(courseSlug, siteCode)
      .then((response) => { if (current) setClassResponse({ key: classRequestKey, results: response.results, error: "" }); })
      .catch((reason: unknown) => {
        if (current) setClassResponse({
          key: classRequestKey,
          results: [],
          error: reason instanceof ApiError ? reason.message : "Không tải được lớp đang mở.",
        });
      });
    return () => { current = false; };
  }, [classRequestKey, courseSlug, siteCode]);

  async function submit(values: EnrollmentValues) {
    setSubmitting(true);
    setError("");
    try {
      setResult(await catalogApi.publicEnroll({
        site_code: values.site_code,
        class_id: values.class_id,
        full_name: values.full_name.trim(),
        email: values.email.trim(),
        phone: values.phone?.trim(),
      }));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Chưa gửi được đăng ký. Vui lòng thử lại.");
    } finally {
      setSubmitting(false);
    }
  }

  return <Modal
    open={Boolean(course)}
    title={course ? `Đăng ký lớp · ${course.name}` : "Đăng ký lớp"}
    onCancel={onClose}
    footer={null}
    width={620}
    destroyOnHidden
  >
    {result ? <div className={styles.enrollmentResult}>
      <Alert type="success" showIcon title={result.message} description={`Cơ sở ${result.site_code} đã ghi nhận đăng ký lớp ${result.class_id}.`} />
      <Button type="primary" onClick={onClose}>Đóng</Button>
    </div> : <>
      <p className={styles.enrollmentIntro}>Chọn cơ sở và lớp còn chỗ. Trung tâm sẽ liên hệ để xác nhận thông tin và cấp tài khoản sau.</p>
      {(error || classError) && <Alert className={styles.enrollmentAlert} type="error" showIcon title={error || classError} />}
      <Form form={form} layout="vertical" onFinish={submit} initialValues={{ site_code: siteCode }}>
        <Form.Item label="Cơ sở học" name="site_code" rules={[{ required: true, message: "Chọn cơ sở học." }]}>
          <Select
            value={siteCode || undefined}
            placeholder="Chọn cơ sở"
            options={course?.branches.map((branch) => ({ value: branch.site_code, label: branch.site_name }))}
            onChange={(value: string) => {
              setSiteCode(value);
              setError("");
              form.setFieldValue("class_id", undefined);
            }}
          />
        </Form.Item>
        <Form.Item label="Lớp đang mở" name="class_id" rules={[{ required: true, message: "Chọn lớp muốn đăng ký." }]}>
          <Select
            placeholder={loadingClasses ? "Đang tải lớp…" : "Chọn lớp còn chỗ"}
            loading={loadingClasses}
            disabled={loadingClasses || classes.length === 0}
            options={classes.map((item) => ({
              value: item.class_id,
              label: `${item.name} · khai giảng ${dateLabel(item.start_date)} · còn ${item.remaining_seats} chỗ`,
            }))}
          />
        </Form.Item>
        {!loadingClasses && !classError && classes.length === 0 && <p className={styles.noOpenClasses}>Cơ sở này hiện chưa có lớp còn chỗ cho khóa học.</p>}
        <Form.Item label="Họ và tên" name="full_name" rules={[{ required: true, whitespace: true, message: "Nhập họ và tên." }, { max: 150, message: "Họ tên tối đa 150 ký tự." }]}>
          <Input autoComplete="name" maxLength={150} placeholder="Nguyễn Văn A" />
        </Form.Item>
        <Form.Item label="Email" name="email" rules={[{ required: true, type: "email", message: "Nhập email hợp lệ để cơ sở liên hệ." }, { max: 254, message: "Email quá dài." }]}>
          <Input autoComplete="email" maxLength={254} placeholder="email@example.com" />
        </Form.Item>
        <Form.Item label="Số điện thoại" name="phone" rules={[{ pattern: /^[+0-9(). -]{0,20}$/, message: "Số điện thoại không hợp lệ." }]}>
          <Input autoComplete="tel" maxLength={20} placeholder="0912 345 678" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={submitting} disabled={!classes.length || loadingClasses} block>
          Gửi đăng ký
        </Button>
      </Form>
    </>}
  </Modal>;
}
