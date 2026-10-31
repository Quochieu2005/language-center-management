"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Card, Col, Empty, Row, Skeleton, Space, Statistic, Tag, Typography } from "antd";
import { academicsApi } from "@/lib/api/academics";
import { adminApi, type SiteCounts } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";

type DashboardState = { health: string; report: SiteCounts | null; notices: Record<string, unknown>[]; errors: string[] };

export default function DashboardPage() {
  const { user } = useSession();
  const [data, setData] = useState<DashboardState | null>(null);
  useEffect(() => {
    let cancelled = false;
    const role = user?.role;
    const isAdmin = role === "admin_big" || role === "admin_small";
    Promise.allSettled([academicsApi.health(), isAdmin ? adminApi.studentCounts() : Promise.resolve(null), isAdmin ? adminApi.notifications({ limit: 8 }) : Promise.resolve(null)]).then((results) => {
      if (cancelled) return;
      const errors: string[] = [];
      let report: SiteCounts | null = null;
      let notices: Record<string, unknown>[] = [];
      const health = results[0].status === "fulfilled" ? String(results[0].value.status || "Đang chạy") : "Không kết nối";
      if (results[0].status === "rejected") errors.push(errorText(results[0].reason));
      if (results[1].status === "fulfilled") report = results[1].value;
      else if (results[1].status === "rejected") {
        if (results[1].reason instanceof ApiError && Array.isArray(results[1].reason.payload.results)) report = results[1].reason.payload as unknown as SiteCounts;
        errors.push(errorText(results[1].reason));
      }
      if (results[2].status === "fulfilled" && results[2].value) notices = results[2].value.results;
      else if (results[2].status === "rejected") errors.push(errorText(results[2].reason));
      setData({ health, report, notices, errors });
    });
    return () => { cancelled = true; };
  }, [user]);
  if (!data) return <Skeleton active />;
  return <div style={{ display: "grid", gap: 20 }}>
    <div><Typography.Title level={2}>Tổng quan</Typography.Title><Typography.Text type="secondary">Số liệu tải từ API theo phiên và quyền hiện tại.</Typography.Text></div>
    {data.errors.length > 0 && <Alert type="warning" showIcon title="Một số dữ liệu chưa tải được" description={data.errors.join(" · ")} />}
    {data.report && !data.report.complete && <Alert type="warning" showIcon title={`Global Query thiếu site: ${data.report.missing_sites.join(", ")}`} />}
    <Row gutter={[16, 16]}>
      <Col xs={24} md={12}><Card><Statistic title="Trạng thái API" value={data.health} styles={{ content: { color: data.health.toLowerCase().includes("ok") ? "#237b57" : undefined } }} /></Card></Col>
      {data.report && <Col xs={24} md={12}><Card><Statistic title={data.report.complete ? "Học viên đang học" : "Học viên ở site đã phản hồi"} value={data.report.total_active_students} /></Card></Col>}
    </Row>
    {data.report && <Card title="Theo cơ sở"><Space direction="vertical" style={{ width: "100%" }}>{data.report.results.map((item) => <div key={item.site_code} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span>{item.site_code}</span><Tag>{item.active_students} học viên</Tag></div>)}</Space></Card>}
    <Card title="Thông báo mới">{data.notices.length ? <Space direction="vertical" style={{ width: "100%" }}>{data.notices.map((item, index) => <div key={String(item.slug ?? index)} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><div><Typography.Text strong>{String(item.title || "Thông báo")}</Typography.Text><br /><Typography.Text type="secondary">{String(item.message || "")}</Typography.Text></div><Tag>{String(item.site_code || "")}</Tag></div>)}</Space> : <Empty description="API chưa trả thông báo nào." />}</Card>
    <Card title="Đi tới nghiệp vụ"><SpaceLinks /></Card>
  </div>;
}

function SpaceLinks() {
  const { user } = useSession();
  const links: { label: string; href: string; roles: string[] }[] = [
    { label: "Học viên", href: "/admin/students", roles: ["admin_big", "admin_small", "tu_van"] },
    { label: "Lớp và đăng ký", href: "/admin/classes", roles: ["admin_big", "admin_small", "le_tan", "xep_lop", "tu_van"] },
    { label: "Học phí", href: "/admin/tuition", roles: ["admin_big", "admin_small", "ke_toan"] },
    { label: "Chuyển cơ sở", href: "/admin/transfers", roles: ["admin_big", "admin_small"] },
    { label: "Giáo viên", href: "/admin/teachers", roles: ["admin_big", "admin_small"] },
    { label: "Tài khoản", href: "/admin/accounts", roles: ["admin_big", "admin_small"] },
    { label: "Báo cáo", href: "/admin/reports", roles: ["admin_big", "admin_small"] },
  ];
  return <Row gutter={[12, 12]}>{links.filter((item) => item.roles.includes(user?.role || "")).map(({ label, href }) => <Col key={href}><Link href={href}>{label}</Link></Col>)}</Row>;
}

function errorText(error: unknown) { return error instanceof Error ? error.message : "API lỗi không xác định."; }
