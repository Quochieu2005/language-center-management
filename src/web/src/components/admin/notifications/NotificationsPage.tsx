"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useRouter } from "next/navigation";
import { adminApi, type AdminNotification, type AdminNotificationList } from "@/lib/api/admin";
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

  return <Card
    title="Thông báo hệ thống"
    extra={<Space>
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
  </Card>;
}
