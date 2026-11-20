"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Col, Row, Statistic, Table, Tag } from "antd";
import { adminApi, type SiteCounts, type TuitionFinancialReport } from "@/lib/api/admin";
import { useSession } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/client";

export default function ReportsPage() {
  const { user } = useSession();
  return <>
    {user?.role !== "ke_toan" && <StudentCountsReport isAdminSmall={user?.role === "admin_small"} />}
    <TuitionFinanceReport />
  </>;
}

function StudentCountsReport({ isAdminSmall }: { isAdminSmall: boolean }) {
  const [data, setData] = useState<SiteCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await adminApi.studentCounts()); setError(""); }
    catch (reason) {
      if (reason instanceof ApiError && Array.isArray(reason.payload.results)) setData(reason.payload as unknown as SiteCounts);
      setError(reason instanceof Error ? reason.message : "Không tải được báo cáo.");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);
  return <Card title="Thống kê học viên theo cơ sở" extra={<Button onClick={() => void load()}>Tải lại</Button>} style={{ marginBottom: 16 }}>
    {error && <Alert type="warning" showIcon title={error} description="Giữ nguyên trạng thái thiếu site; không xem số liệu một phần là tổng đầy đủ." style={{ marginBottom: 16 }} />}
    {data && <>
      {!data.complete && <Alert type="warning" showIcon title={`Thiếu site: ${data.missing_sites.join(", ")}`} style={{ marginBottom: 16 }} />}
      <Statistic title={data.complete ? "Tổng học viên đang học" : "Tổng của các site đã phản hồi (chưa đầy đủ)"} value={data.total_active_students} style={{ marginBottom: 24 }} />
      <Table rowKey="site_code" loading={loading} dataSource={data.results} pagination={false} columns={[{ title: "Cơ sở", dataIndex: "site_code" }, { title: "Đang học", dataIndex: "active_students" }, { title: "Phạm vi", render: () => <Tag color={data.scope === "GLOBAL" ? "blue" : "default"}>{data.scope}</Tag> }]} />
    </>}
    {isAdminSmall && <Alert type="info" title="Admin Small chỉ xem số liệu cơ sở được phân công; API đã giới hạn phạm vi." style={{ marginTop: 16 }} />}
  </Card>;
}

function TuitionFinanceReport() {
  const [data, setData] = useState<TuitionFinancialReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await adminApi.tuitionFinancialSummary()); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được báo cáo tài chính."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);
  return <Card title="Báo cáo tài chính học phí" extra={<Button onClick={() => void load()}>Tải lại</Button>}>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}
    {data && <>
      {!data.complete && <Alert type="warning" showIcon title={`Thiếu site: ${data.missing_sites.join(", ")}. Các tổng bên dưới chỉ tính site đã phản hồi.`} style={{ marginBottom: 16 }} />}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} xl={8}><Statistic title="Tổng phải thu" value={data.totals.total_due} formatter={(value) => money(Number(value))} /></Col>
        <Col xs={24} sm={12} xl={8}><Statistic title="Đã thu ròng" value={data.totals.net_collected} formatter={(value) => money(Number(value))} /></Col>
        <Col xs={24} sm={12} xl={8}><Statistic title="Còn nợ" value={data.totals.outstanding} formatter={(value) => money(Number(value))} /></Col>
        <Col xs={24} sm={12} xl={8}><Statistic title="Tổng phiếu thu" value={data.totals.total_collected} formatter={(value) => money(Number(value))} /></Col>
        <Col xs={24} sm={12} xl={8}><Statistic title="Tổng phiếu hoàn" value={data.totals.total_refunded} formatter={(value) => money(Number(value))} /></Col>
        <Col xs={24} sm={12} xl={8}><Statistic title="Số khoản học phí" value={data.totals.tuition_accounts} /></Col>
        <Col xs={24} sm={12} xl={8}><Statistic title="Khoản còn nợ" value={data.totals.accounts_with_balance} /></Col>
      </Row>
      <Table rowKey="site_code" loading={loading} dataSource={data.results} pagination={false} scroll={{ x: 900 }} columns={[
        { title: "Cơ sở", dataIndex: "site_code" },
        { title: "Khoản học phí", dataIndex: "tuition_accounts" },
        { title: "Phải thu", dataIndex: "total_due", render: money },
        { title: "Đã thu", dataIndex: "total_collected", render: money },
        { title: "Đã hoàn", dataIndex: "total_refunded", render: money },
        { title: "Còn nợ", dataIndex: "outstanding", render: money },
        { title: "Khoản còn nợ", dataIndex: "accounts_with_balance" },
        { title: "Phạm vi", render: () => <Tag color={data.scope === "GLOBAL" ? "blue" : "default"}>{data.scope}</Tag> },
      ]} />
    </>}
  </Card>;
}

function money(value: unknown) {
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(Number(value) || 0);
}
