"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, DatePicker, Form, Input, Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { adminApi, type AdminAuditLog, type AdminAuditLogList } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useSiteScope } from "@/lib/auth/site-scope";

const PAGE_SIZE = 20;
const logLabels: Record<AdminAuditLog["log_type"], string> = {
  login: "Đăng nhập",
  password_reset: "Đặt lại mật khẩu",
  system: "Thao tác hệ thống",
  sync: "Đồng bộ",
};

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Ho_Chi_Minh" }).format(date);
}

type Filters = { account_id?: string; log_type?: string; from_date?: string; to_date?: string };

export default function AuditPage() {
  const { user } = useSession();
  const { siteCodes } = useSiteScope();
  const [form] = Form.useForm();
  const [logs, setLogs] = useState<AdminAuditLogList | null>(null);
  const [siteFilter, setSiteFilter] = useState("all");
  const [filters, setFilters] = useState<Filters>({});
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const isAdminBig = user?.role === "admin_big";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setLogs(await adminApi.auditLogs({
        site_code: isAdminBig && siteFilter !== "all" ? siteFilter : undefined,
        ...filters,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được nhật ký.");
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) {
        const partial = reason.payload as unknown as AdminAuditLogList;
        setLogs({ ...partial, complete: false, missing_sites: partial.missing_sites || [] });
      }
    } finally {
      setLoading(false);
    }
  }, [filters, isAdminBig, page, siteFilter]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const columns: ColumnsType<AdminAuditLog> = [
    { title: "Thời điểm (GMT+7)", dataIndex: "occurred_at", render: formatTime },
    { title: "Cơ sở", dataIndex: "site_code" },
    { title: "Tài khoản", dataIndex: "account_id", render: (value: string | null) => value || "Hệ thống" },
    { title: "Loại", dataIndex: "log_type", render: (value: AdminAuditLog["log_type"]) => logLabels[value] || value },
    { title: "Thao tác", dataIndex: "action", render: (value: string | null) => value || "—" },
    { title: "Bảng", dataIndex: "affected_table", render: (value: string | null) => value || "—" },
    { title: "Mã bản ghi", dataIndex: "record_id", render: (value: string | null) => value || "—" },
    { title: "Kết quả", dataIndex: "result", render: (value: string | null) => value
      ? <Tag color={value === "thanh_cong" ? "green" : "red"}>{value === "thanh_cong" ? "Thành công" : "Thất bại"}</Tag>
      : "—" },
  ];

  return <Card title="Nhật ký Admin" extra={<Button onClick={() => void load()}>Tải lại</Button>}>
    <Form form={form} layout="inline" onFinish={(values) => {
      setFilters({
        account_id: values.account_id?.trim() || undefined,
        log_type: values.log_type || undefined,
        from_date: values.date_range?.[0]?.format("YYYY-MM-DD"),
        to_date: values.date_range?.[1]?.format("YYYY-MM-DD"),
      });
      setPage(1);
    }} style={{ gap: 8, rowGap: 8, marginBottom: 16 }}>
      {isAdminBig && <Select
        aria-label="Lọc nhật ký theo cơ sở"
        value={siteFilter}
        onChange={(value: string) => { setSiteFilter(value); setPage(1); }}
        options={[{ value: "all", label: "Toàn hệ thống" }, ...siteCodes.map((site) => ({ value: site, label: site }))]}
        style={{ minWidth: 150 }}
      />}
      <Form.Item name="account_id"><Input placeholder="Mã tài khoản" maxLength={24} allowClear /></Form.Item>
      <Form.Item name="log_type"><Select allowClear placeholder="Tất cả loại nhật ký" style={{ minWidth: 190 }} options={Object.entries(logLabels).map(([value, label]) => ({ value, label }))} /></Form.Item>
      <Form.Item name="date_range"><DatePicker.RangePicker format="DD/MM/YYYY" /></Form.Item>
      <Button type="primary" htmlType="submit">Lọc</Button>
    </Form>
    {error && <Alert type="warning" showIcon title={error} style={{ marginBottom: 16 }} />}
    {logs && !logs.complete && <Alert
      type="warning"
      showIcon
      title={`Nhật ký chưa đầy đủ; không nhận được dữ liệu từ: ${logs.missing_sites.join(", ") || "một số cơ sở"}.`}
      style={{ marginBottom: 16 }}
    />}
    <Table
      rowKey={(item) => `${item.site_code}:${item.log_id}`}
      loading={loading}
      columns={columns}
      dataSource={logs?.results || []}
      scroll={{ x: 1050 }}
      pagination={{
        current: page, pageSize: PAGE_SIZE, total: logs?.count || 0, showSizeChanger: false,
        onChange: setPage,
      }}
    />
  </Card>;
}
