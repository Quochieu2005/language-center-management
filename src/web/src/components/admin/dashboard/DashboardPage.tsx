"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Empty, Row, Skeleton, Statistic, Tag, Typography } from "antd";
import styles from "./DashboardPage.module.scss";
import { academicsApi } from "@/lib/api/academics";
import { adminApi, type SiteCounts } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import type { Role } from "@/lib/api/auth";

const classStatusOptions = [
  { status: "sap_mo", label: "Sắp mở", color: "#d97706" },
  { status: "dang_hoc", label: "Đang học", color: "#237b57" },
  { status: "ket_thuc", label: "Kết thúc", color: "#3b82f6" },
  { status: "huy", label: "Đã hủy", color: "#64748b" },
] as const;

type ClassStatusMetric = (typeof classStatusOptions)[number] & { count: number };

export default function DashboardPage() {
  const { user, loading } = useSession();
  if (loading) return <Skeleton active />;
  if (user?.role === "admin_big") return <AdminBigDashboard />;
  if (user?.role === "admin_small") return <AdminSmallDashboard siteCode={user.site_code} />;
  return <StaffDashboard role={user?.role} />;
}

function AdminBigDashboard() {
  const [report, setReport] = useState<SiteCounts | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      adminApi.studentCounts().then((result) => {
        if (active) setReport(result);
      }).catch((reason: unknown) => {
        if (!active) return;
        const partial = partialSiteCounts(reason);
        if (partial) setReport(partial);
        setError(errorText(reason));
      }).finally(() => {
        if (active) setLoading(false);
      });
    });
    return () => { active = false; };
  }, [reload]);

  const title = report?.complete ? "Học viên đang học toàn hệ thống" : "Học viên tại site đã phản hồi";
  return <div className={styles.dashboardContainer}>
    <DashboardHeader
      badge="ADMIN BIG"
      title="Thống kê toàn trung tâm"
      description="Tổng hợp số học viên đang học từ các CSDL site riêng."
    />
    {report && !report.complete && <Alert
      type="warning"
      showIcon
      title="Số liệu chưa đầy đủ"
      description={`Chưa đọc được các site: ${report.missing_sites.join(", ") || "chưa xác định"}. Tổng hiện tại chỉ gồm các site đã phản hồi.`}
    />}
    {error && <Alert type={report?.complete ? "warning" : "error"} showIcon title="Không tải được dữ liệu mới" description={error} />}
    {loading && !report ? <Skeleton active /> : <>
      {report && <Row gutter={[16, 16]}>
        <Col xs={24} md={8}><MetricCard title={title} value={report.total_active_students} /></Col>
        <Col xs={24} md={8}><MetricCard title="Cơ sở đang hoạt động" value={report.site_codes.length} /></Col>
        <Col xs={24} md={8}><MetricCard title="Cơ sở đã phản hồi" value={`${report.results.length}/${report.site_codes.length}`} /></Col>
      </Row>}
      <Card
        className={styles.dashboardChartCard}
        title="Học viên đang học theo cơ sở"
        extra={<Button onClick={() => { setLoading(true); setError(""); setReload((value) => value + 1); }} loading={loading}>Tải lại</Button>}
      >
        {report?.results.length ? <SiteStudentChart results={report.results} /> : <Empty description={loading ? "Đang tải số liệu..." : "Chưa có số liệu cơ sở để hiển thị."} />}
        {report && <Typography.Text type="secondary" className={styles.chartNote}>
          Nguồn: `HocVien` tại từng site; chỉ tính hồ sơ `dang_hoc`. Mỗi CSDL được hỏi riêng, không gộp vào database trung tâm.
        </Typography.Text>}
      </Card>
      <Card title="Đi tới nghiệp vụ"><SpaceLinks role="admin_big" /></Card>
    </>}
  </div>;
}

function AdminSmallDashboard({ siteCode }: { siteCode: string | null }) {
  const [report, setReport] = useState<SiteCounts | null>(null);
  const [classes, setClasses] = useState<ClassStatusMetric[] | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    if (!siteCode) {
      queueMicrotask(() => {
        if (active) {
          setErrors(["Tài khoản chưa được gán cơ sở."]);
          setLoading(false);
        }
      });
      return () => { active = false; };
    }
    queueMicrotask(() => {
      if (!active) return;
      setErrors([]);
      Promise.allSettled([
        adminApi.studentCounts(siteCode),
        Promise.all(classStatusOptions.map(async (item) => {
          const result = await academicsApi.classes(siteCode, { status: item.status, limit: 1, offset: 0 });
          return { ...item, count: result.count };
        })),
      ]).then(([studentsResult, classesResult]) => {
        if (!active) return;
        const nextErrors: string[] = [];
        if (studentsResult.status === "fulfilled") setReport(studentsResult.value);
        else nextErrors.push(`Thống kê học viên: ${errorText(studentsResult.reason)}`);
        if (classesResult.status === "fulfilled") setClasses(classesResult.value);
        else nextErrors.push(`Thống kê lớp: ${errorText(classesResult.reason)}`);
        setErrors(nextErrors);
      }).finally(() => {
        if (active) setLoading(false);
      });
    });
    return () => { active = false; };
  }, [siteCode, reload]);

  const activeClasses = classes?.find((item) => item.status === "dang_hoc")?.count;
  const upcomingClasses = classes?.find((item) => item.status === "sap_mo")?.count;
  return <div className={styles.dashboardContainer}>
    <DashboardHeader
      badge={`ADMIN SMALL${siteCode ? ` · ${siteCode}` : ""}`}
      title="Thống kê cơ sở"
      description="Số liệu chỉ đọc từ cơ sở được gán cho tài khoản của bạn."
    />
    {errors.map((message) => <Alert key={message} type="warning" showIcon title={message} />)}
    {loading && !report && !classes ? <Skeleton active /> : <>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}><MetricCard title="Học viên đang học tại cơ sở" value={report?.total_active_students ?? "—"} /></Col>
        <Col xs={24} md={8}><MetricCard title="Lớp đang học" value={activeClasses ?? "—"} /></Col>
        <Col xs={24} md={8}><MetricCard title="Lớp sắp mở" value={upcomingClasses ?? "—"} /></Col>
      </Row>
      <Card
        className={styles.dashboardChartCard}
        title={`Tình trạng lớp${siteCode ? ` · ${siteCode}` : ""}`}
        extra={<Button onClick={() => { setLoading(true); setErrors([]); setReload((value) => value + 1); }} loading={loading}>Tải lại</Button>}
      >
        {classes ? <ClassStatusChart data={classes} /> : <Empty description={loading ? "Đang tải số liệu..." : "Chưa lấy được số liệu lớp."} />}
        <Typography.Text type="secondary" className={styles.chartNote}>
          Nguồn: số lớp theo trạng thái `sap_mo`, `dang_hoc`, `ket_thuc`, `huy` trong CSDL của cơ sở này.
        </Typography.Text>
      </Card>
      {report?.complete === false && <Alert type="warning" showIcon title={`Dữ liệu site chưa đầy đủ: ${report.missing_sites.join(", ")}`} />}
      <Card title="Đi tới nghiệp vụ"><SpaceLinks role="admin_small" /></Card>
    </>}
  </div>;
}

function DashboardHeader({ badge, title, description }: { badge: string; title: string; description: string }) {
  return <header className={styles.dashboardHeader}>
    <div>
      <Typography.Title level={2}>{title}</Typography.Title>
      <Typography.Text type="secondary">{description}</Typography.Text>
    </div>
    <Tag color="blue" className={styles.roleBadge}>{badge}</Tag>
  </header>;
}

function MetricCard({ title, value }: { title: string; value: number | string }) {
  return <Card className={styles.dashboardMetricCard}><Statistic title={title} value={value} /></Card>;
}

function SiteStudentChart({ results }: { results: SiteCounts["results"] }) {
  const maximum = Math.max(1, ...results.map((item) => item.active_students));
  return <div className={styles.siteChart} role="list" aria-label="Số học viên đang học theo cơ sở">
    {results.map((item) => {
      const percent = Math.round((item.active_students / maximum) * 100);
      return <div className={styles.siteBarRow} key={item.site_code} role="listitem">
        <div className={styles.siteBarLabel}><span>{item.site_code}</span><strong>{formatCount(item.active_students)}</strong></div>
        <div className={styles.siteBarTrack} role="meter" aria-label={`${item.site_code}: ${formatCount(item.active_students)} học viên`} aria-valuemin={0} aria-valuemax={maximum} aria-valuenow={item.active_students}>
          <span className={styles.siteBarFill} style={{ width: `${percent}%` }} />
        </div>
      </div>;
    })}
    <Typography.Text type="secondary" className={styles.chartNote}>Thanh biểu thị tương quan giữa các cơ sở đang hiển thị.</Typography.Text>
  </div>;
}

function ClassStatusChart({ data }: { data: ClassStatusMetric[] }) {
  const maximum = Math.max(1, ...data.map((item) => item.count));
  return <div className={styles.classChart} role="list" aria-label="Số lớp theo trạng thái">
    {data.map((item) => {
      const percent = Math.round((item.count / maximum) * 100);
      return <div className={styles.classBarItem} key={item.status} role="listitem">
        <strong>{formatCount(item.count)}</strong>
        <div className={styles.classBarTrack} role="meter" aria-label={`${item.label}: ${formatCount(item.count)} lớp`} aria-valuemin={0} aria-valuemax={maximum} aria-valuenow={item.count}>
          <span className={styles.classBarFill} style={{ height: `${percent}%`, backgroundColor: item.color }} />
        </div>
        <span className={styles.classBarLabel}>{item.label}</span>
      </div>;
    })}
  </div>;
}

function StaffDashboard({ role }: { role?: Role }) {
  return <div className={styles.dashboardContainer}>
    <DashboardHeader badge="WORKSPACE" title="Tổng quan nghiệp vụ" description="Chọn chức năng theo quyền được cấp." />
    <Card title="Đi tới nghiệp vụ"><SpaceLinks role={role} /></Card>
  </div>;
}

function SpaceLinks({ role }: { role?: Role }) {
  const links: { label: string; href: string; roles: Role[] }[] = [
    { label: "Học viên", href: "/admin/students", roles: ["admin_big", "admin_small", "tu_van"] },
    { label: "Lớp và đăng ký", href: "/admin/classes", roles: ["admin_big", "admin_small", "le_tan", "tu_van"] },
    { label: "Học phí", href: "/admin/tuition", roles: ["admin_big", "admin_small", "ke_toan"] },
    { label: "Chuyển cơ sở", href: "/admin/transfers", roles: ["admin_big", "admin_small"] },
    { label: "Giáo viên", href: "/admin/teachers", roles: ["admin_big", "admin_small"] },
    { label: "Nhân viên", href: "/admin/employees", roles: ["admin_big", "admin_small"] },
    { label: "Admin Small", href: "/admin/accounts", roles: ["admin_big"] },
    { label: "Thông báo", href: "/admin/notifications", roles: ["admin_big", "admin_small"] },
    { label: "Nhật ký Admin", href: "/admin/audit", roles: ["admin_big", "admin_small"] },
    { label: "Báo cáo", href: "/admin/reports", roles: ["admin_big", "admin_small"] },
  ];
  return <nav className={styles.quickLinks} aria-label="Đi tới nghiệp vụ">
    {links.filter((item) => role && item.roles.includes(role)).map(({ label, href }) => <Link className={styles.quickLink} href={href} key={href}>{label}</Link>)}
  </nav>;
}

function partialSiteCounts(error: unknown): SiteCounts | null {
  if (!(error instanceof ApiError) || !Array.isArray(error.payload.results)) return null;
  return error.payload as unknown as SiteCounts;
}

function formatCount(value: number) {
  return new Intl.NumberFormat("vi-VN").format(value);
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Không tải được số liệu.";
}
