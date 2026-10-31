"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Statistic, Table, Tag } from "antd";
import { adminApi, type SiteCounts } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/client";

export default function ReportsPage() {
  const { user } = useSession();
  const [data, setData] = useState<SiteCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setData(await adminApi.studentCounts()); setError(""); }
    catch (reason) {
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) setData(reason.payload as unknown as SiteCounts);
      setError(reason instanceof Error ? reason.message : "Không tải được báo cáo.");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { let cancelled = false; queueMicrotask(() => { if (!cancelled) void load(); }); return () => { cancelled = true; }; }, [load]);
  return <Card title="Thống kê học viên theo cơ sở" extra={<Button onClick={() => void load()}>Tải lại</Button>}>
    {error && <Alert type="warning" showIcon title={error} description="Giữ nguyên trạng thái thiếu site; không xem số liệu một phần là tổng đầy đủ." style={{ marginBottom: 16 }} />}
    {data && <>
      {!data.complete && <Alert type="warning" showIcon title={`Thiếu site: ${data.missing_sites.join(", ")}`} style={{ marginBottom: 16 }} />}
      <Statistic title={data.complete ? "Tổng học viên đang học" : "Tổng của các site đã phản hồi (chưa đầy đủ)"} value={data.total_active_students} style={{ marginBottom: 24 }} />
      <Table rowKey="site_code" loading={loading} dataSource={data.results} pagination={false} columns={[{ title: "Cơ sở", dataIndex: "site_code" }, { title: "Đang học", dataIndex: "active_students" }, { title: "Phạm vi", render: () => <Tag color={data.scope === "GLOBAL" ? "blue" : "default"}>{data.scope}</Tag> }]} />
    </>}
    {user?.role === "admin_small" && <Alert type="info" title="Admin Small chỉ xem số liệu cơ sở được phân công; API đã giới hạn phạm vi." style={{ marginTop: 16 }} />}
  </Card>;
}
