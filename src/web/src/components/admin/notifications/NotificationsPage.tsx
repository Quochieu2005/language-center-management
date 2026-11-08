"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Form, Input, message as antdMessage, Modal, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useRouter } from "next/navigation";
import { adminApi, type AdminNotification, type AdminNotificationList, type CreateAdminNotification } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

const PAGE_SIZE = 20;
const severityColors: Record<string, string> = { critical: "red", error: "red", warning: "orange", info: "blue", success: "green" };

function formatCreatedAt(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Ho_Chi_Minh" }).format(date);
}

export default function NotificationsPage() {
  const router = useRouter();
  const { user } = useSession();
  const { siteCodes } = useSiteScope();
  const [data, setData] = useState<AdminNotificationList | null>(null);
  const [siteFilter, setSiteFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createMissingSites, setCreateMissingSites] = useState<string[]>([]);
  const [form] = Form.useForm<CreateAdminNotification>();
  const submission = useRef<{ signature: string; key: string } | null>(null);
  const isAdminBig = user?.role === "admin_big";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await adminApi.notifications({
        site_code: isAdminBig && siteFilter !== "all" ? siteFilter : undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setData(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được thông báo.");
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) {
        const payload = reason.payload as unknown as AdminNotificationList;
        setData({ ...payload, complete: false, missing_sites: payload.missing_sites || [] });
      }
    } finally {
      setLoading(false);
    }
  }, [isAdminBig, page, siteFilter]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const columns: ColumnsType<AdminNotification> = [
    {
      title: "Thông báo",
      dataIndex: "title",
      render: (title: string, item) => <div>
        <Typography.Text strong>{title}</Typography.Text>
        <Typography.Paragraph type="secondary" style={{ margin: "4px 0 0" }}>{item.message}</Typography.Paragraph>
      </div>,
    },
    { title: "Nhóm", dataIndex: "category", render: (category: string) => <Tag>{category}</Tag> },
    { title: "Mức độ", dataIndex: "severity", render: (severity: string) => <Tag color={severityColors[severity] || "default"}>{severity}</Tag> },
    { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Thời điểm", dataIndex: "created_at", render: formatCreatedAt },
    {
      title: "",
      render: (_value, item) => item.target_path?.startsWith("/")
        ? <Button type="link" onClick={() => router.push(item.target_path!)}>Mở</Button>
        : null,
    },
  ];

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({ category: "system", severity: "info", audience: "admin_all", title: "", message: "", target_path: null });
    setCreateError("");
    setCreateMissingSites([]);
    submission.current = null;
    setCreating(true);
  };

  const closeCreate = () => {
    if (saving) return;
    setCreating(false);
    setCreateError("");
    setCreateMissingSites([]);
    submission.current = null;
  };

  const submitCreate = async (values: CreateAdminNotification) => {
    const body = { ...values, target_path: values.target_path?.trim() || null };
    const signature = JSON.stringify(body);
    if (!submission.current || submission.current.signature !== signature) {
      submission.current = { signature, key: crypto.randomUUID() };
    }
    setSaving(true);
    setCreateError("");
    try {
      const result = await adminApi.createNotification(body, submission.current.key);
      if (!result.complete) {
        setCreateMissingSites(result.missing_sites);
        await load();
        return;
      }
      antdMessage.success(`Đã tạo thông báo tại ${result.site_codes.length} cơ sở.`);
      submission.current = null;
      setCreating(false);
      form.resetFields();
      await load();
    } catch (reason) {
      setCreateError(reason instanceof Error ? reason.message : "Không tạo được thông báo.");
    } finally {
      setSaving(false);
    }
  };

  return <Card
    title="Thông báo hệ thống"
    extra={<Space wrap>
      <Button type="primary" onClick={openCreate}>Tạo thông báo</Button>
      {isAdminBig && <Select
        aria-label="Lọc thông báo theo cơ sở"
        value={siteFilter}
        onChange={(value: string) => { setSiteFilter(value); setPage(1); }}
        options={[{ value: "all", label: "Toàn hệ thống" }, ...siteCodes.map((site) => ({ value: site, label: site }))]}
        style={{ minWidth: 160 }}
      />}
      <Button onClick={() => void load()}>Tải lại</Button>
    </Space>}
  >
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    {data && !data.complete && <Alert
      type="warning"
      showIcon
      title={`Danh sách chưa đầy đủ; không nhận được dữ liệu từ: ${data.missing_sites.join(", ") || "một số cơ sở"}.`}
      style={{ marginBottom: 16 }}
    />}
    <Table
      rowKey={(item) => `${item.site_code}:${item.slug}`}
      loading={loading}
      columns={columns}
      dataSource={data?.results || []}
      scroll={{ x: 850 }}
      pagination={{
        current: page,
        pageSize: PAGE_SIZE,
        total: data?.count || 0,
        showSizeChanger: false,
        onChange: setPage,
      }}
    />
    <Modal
      title="Tạo thông báo"
      open={creating}
      onCancel={closeCreate}
      footer={null}
      destroyOnHidden
    >
      <Typography.Paragraph type="secondary">
        {isAdminBig
          ? "Thông báo được ghi tới các cơ sở đang hoạt động. Nếu thiếu cơ sở, giữ nguyên nội dung và gửi lại để hoàn tất."
          : `Thông báo chỉ được ghi tại cơ sở ${user?.site_code || "được cấp"}.`}
      </Typography.Paragraph>
      {createMissingSites.length > 0 && <Alert
        type="warning"
        showIcon
        title={`Chưa ghi được tại: ${createMissingSites.join(", ")}. Giữ nguyên nội dung rồi bấm tạo lại để retry an toàn.`}
        style={{ marginBottom: 16 }}
      />}
      {createError && <Alert type="error" showIcon title={createError} style={{ marginBottom: 16 }} />}
      <Form
        form={form}
        layout="vertical"
        onFinish={submitCreate}
        onValuesChange={() => { setCreateError(""); setCreateMissingSites([]); }}
      >
        <Form.Item name="title" label="Tiêu đề" rules={[{ required: true, whitespace: true }, { max: 160 }]}>
          <Input maxLength={160} showCount />
        </Form.Item>
        <Form.Item name="message" label="Nội dung" rules={[{ max: 500 }]}>
          <Input.TextArea rows={4} maxLength={500} showCount />
        </Form.Item>
        <Space orientation="horizontal" size="middle" style={{ display: "flex" }}>
          <Form.Item name="category" label="Nhóm" rules={[{ required: true }]} style={{ flex: 1 }}>
            <Select options={[
              { value: "system", label: "Hệ thống" }, { value: "tuition", label: "Học phí" },
              { value: "account", label: "Tài khoản" }, { value: "teacher", label: "Giáo viên" },
              { value: "enrollment", label: "Đăng ký" }, { value: "class", label: "Lớp học" },
              { value: "grade", label: "Điểm" }, { value: "transfer", label: "Chuyển cơ sở" },
              { value: "payment", label: "Thanh toán" }, { value: "security", label: "Bảo mật" },
            ]} />
          </Form.Item>
          <Form.Item name="severity" label="Mức độ" rules={[{ required: true }]} style={{ flex: 1 }}>
            <Select options={[
              { value: "info", label: "Thông tin" }, { value: "success", label: "Thành công" },
              { value: "warning", label: "Cảnh báo" }, { value: "critical", label: "Khẩn cấp" },
            ]} />
          </Form.Item>
        </Space>
        <Form.Item name="audience" label="Nhóm nhận" rules={[{ required: true }]}>
          <Select options={[
            { value: "admin_all", label: "Admin Big và Admin Small" },
            ...(isAdminBig ? [{ value: "admin_big" as const, label: "Chỉ Admin Big" }] : []),
            { value: "admin_small", label: "Admin Small" },
          ]} />
        </Form.Item>
        <Form.Item name="target_path" label="Đường dẫn trong trang quản trị (không bắt buộc)">
          <Input maxLength={300} placeholder="/admin/tuition" />
        </Form.Item>
        <Space orientation="horizontal" style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button onClick={closeCreate} disabled={saving}>Hủy</Button>
          <Button type="primary" htmlType="submit" loading={saving}>Tạo thông báo</Button>
        </Space>
      </Form>
    </Modal>
  </Card>;
}
