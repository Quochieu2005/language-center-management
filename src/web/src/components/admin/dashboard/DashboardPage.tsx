"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOutlined,
  CalendarOutlined,
  DollarCircleOutlined,
  ReloadOutlined,
  SwapOutlined,
  TeamOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { Alert, Skeleton } from "antd";
import { academicsApi, type ClassRow, type TransferRow, type TuitionRow } from "@/lib/api/academics";
import {
  adminApi,
  type AdminAuditLog,
  type SiteCounts,
  type TuitionFinancialReport,
} from "@/lib/api/admin";
import type { Role } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { ALL_SITES, useSiteScope } from "@/lib/auth/site-scope";
import styles from "./AdminDashboard.module.scss";
import {
  ComboBarLineChart,
  DonutChartCard,
  KpiSparkCard,
  type ComboPoint,
  type DonutSegment,
} from "./DashboardCharts";
import { DistributedClusterCard, RecentActivityCard, TopClassesCard } from "./DashboardWidgets";

function formatVnd(val: number): string {
  return `${new Intl.NumberFormat("vi-VN").format(Math.round(val))}đ`;
}

function formatAxisCompact(val: number): string {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(val % 1_000_000 === 0 ? 0 : 1)}M`;
  if (val >= 1_000) return `${Math.round(val / 1_000)}K`;
  return String(val);
}

function extractPartial<T>(reason: unknown): T | null {
  if (reason instanceof ApiError && reason.payload && typeof reason.payload === "object") {
    return reason.payload as unknown as T;
  }
  return null;
}

export default function DashboardPage() {
  const { user, loading } = useSession();
  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />;
  if (user?.role === "admin_big" || user?.role === "admin_small") {
    return <AdminAnalyticsDashboard />;
  }
  return <StaffDashboard role={user?.role} siteCode={user?.site_code ?? null} username={user?.username} />;
}

function AdminAnalyticsDashboard() {
  const { user } = useSession();
  const { selectedSite, loadingSites } = useSiteScope();
  const isAdminBig = user?.role === "admin_big";

  const apiSiteParam = isAdminBig && selectedSite && selectedSite !== ALL_SITES ? selectedSite : undefined;

  const [studentCounts, setStudentCounts] = useState<SiteCounts | null>(null);
  const [tuitionReport, setTuitionReport] = useState<TuitionFinancialReport | null>(null);
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [tuitionRows, setTuitionRows] = useState<TuitionRow[]>([]);
  const [transfers, setTransfers] = useState<TransferRow[]>([]);
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [comboMode, setComboMode] = useState<"activity" | "finance" | "classes">("activity");
  const [donutMode, setDonutMode] = useState<"tuition" | "classes">("tuition");

  const loadDashboard = useCallback(async () => {
    if (isAdminBig && loadingSites) return;
    setLoading(true);
    setErrors([]);

    const [studentsRes, tuitionSumRes, classesRes, tuitionListRes, transfersRes, logsRes] =
      await Promise.allSettled([
        adminApi.studentCounts(apiSiteParam),
        adminApi.tuitionFinancialSummary(apiSiteParam),
        academicsApi.classes(apiSiteParam, { limit: 100 }),
        academicsApi.tuition(apiSiteParam, { limit: 100 }),
        academicsApi.transfers({ site_code: apiSiteParam }),
        adminApi.auditLogs({ site_code: apiSiteParam, limit: 100 }),
      ]);

    const nextErrors: string[] = [];

    if (studentsRes.status === "fulfilled") {
      setStudentCounts(studentsRes.value);
    } else {
      const partial = extractPartial<SiteCounts>(studentsRes.reason);
      if (partial && Array.isArray(partial.results)) setStudentCounts(partial);
      nextErrors.push(studentsRes.reason instanceof Error ? studentsRes.reason.message : "Lỗi thống kê học viên");
    }

    if (tuitionSumRes.status === "fulfilled") {
      setTuitionReport(tuitionSumRes.value);
    } else {
      const partial = extractPartial<TuitionFinancialReport>(tuitionSumRes.reason);
      if (partial && partial.totals) setTuitionReport(partial);
      nextErrors.push(tuitionSumRes.reason instanceof Error ? tuitionSumRes.reason.message : "Lỗi báo cáo học phí");
    }

    if (classesRes.status === "fulfilled") {
      setClasses(classesRes.value.results || []);
    } else {
      const partial = extractPartial<{ results?: ClassRow[] }>(classesRes.reason);
      setClasses(Array.isArray(partial?.results) ? partial.results : []);
    }

    if (tuitionListRes.status === "fulfilled") {
      setTuitionRows(tuitionListRes.value.results || []);
    } else {
      const partial = extractPartial<{ results?: TuitionRow[] }>(tuitionListRes.reason);
      setTuitionRows(Array.isArray(partial?.results) ? partial.results : []);
    }

    if (transfersRes.status === "fulfilled") {
      setTransfers(transfersRes.value.results || []);
    } else {
      const partial = extractPartial<{ results?: TransferRow[] }>(transfersRes.reason);
      setTransfers(Array.isArray(partial?.results) ? partial.results : []);
    }

    if (logsRes.status === "fulfilled") {
      setAuditLogs(logsRes.value.results || []);
    } else {
      const partial = extractPartial<{ results?: AdminAuditLog[] }>(logsRes.reason);
      setAuditLogs(Array.isArray(partial?.results) ? partial.results : []);
    }

    setErrors(nextErrors);
    setLoading(false);
  }, [apiSiteParam, isAdminBig, loadingSites]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) void loadDashboard();
    });
    return () => {
      cancelled = true;
    };
  }, [loadDashboard]);

  // Aggregate derived metrics from real DB data
  const totalStudents = studentCounts?.total_active_students ?? 0;
  const activeSitesCount = studentCounts?.site_codes?.length ?? 0;
  const netCollected = tuitionReport?.totals?.net_collected ?? 0;
  const totalDue = tuitionReport?.totals?.total_due ?? 0;
  const outstanding = tuitionReport?.totals?.outstanding ?? 0;
  const accountsWithBalance = tuitionReport?.totals?.accounts_with_balance ?? 0;
  const totalRefunded = tuitionReport?.totals?.total_refunded ?? 0;
  const collectionRate = totalDue > 0 ? Math.round((netCollected / totalDue) * 1000) / 10 : 0;

  const activeClasses = classes.filter((c) => c.status === "dang_hoc").length;
  const totalEnrolled = classes.reduce((acc, c) => acc + (c.current_count || 0), 0);
  const totalCapacity = classes.reduce((acc, c) => acc + (c.capacity || 0), 0);
  const fillRate = totalCapacity > 0 ? Math.round((totalEnrolled / totalCapacity) * 100) : 0;
  const pendingTransfers = transfers.filter((t) => t.status === "cho_duyet").length;

  // Build Daily Activity Points from real dbo.Logs timestamps
  const dailyActivitySeries = useMemo<ComboPoint[]>(() => {
    const byDate = new Map<string, { total: number; success: number }>();
    for (const log of auditLogs) {
      if (!log.occurred_at) continue;
      const d = new Date(log.occurred_at);
      if (Number.isNaN(d.getTime())) continue;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      const cur = byDate.get(key) || { total: 0, success: 0 };
      cur.total += 1;
      if (log.result !== "that_bai") cur.success += 1;
      byDate.set(key, cur);
    }
    const sorted = Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-7);

    return sorted.map(([isoDate, counts]) => {
      const [, mm, dd] = isoDate.split("-");
      return {
        label: `${dd}/${mm}`,
        barValue: counts.total,
        lineValue: counts.success,
        tooltipTitle: `Ngày ${dd}/${mm}`,
        barLabel: "Tổng thao tác",
        lineLabel: "Thành công",
      };
    });
  }, [auditLogs]);

  const financeComboSeries = useMemo<ComboPoint[]>(() => {
    const siteResults = tuitionReport?.results ?? [];
    if (siteResults.length > 1) {
      return siteResults.map((r) => ({
        label: r.site_code,
        barValue: r.net_collected,
        lineValue: r.total_due,
        tooltipTitle: `Cơ sở ${r.site_code}`,
        barLabel: "Đã thu ròng",
        lineLabel: "Tổng phải thu",
      }));
    }
    return tuitionRows.slice(0, 7).map((row) => ({
      label: row.class_name.length > 12 ? `${row.class_name.slice(0, 12)}…` : row.class_name,
      barValue: row.amount_paid,
      lineValue: row.total_due,
      tooltipTitle: `${row.student_name} (${row.class_name})`,
      barLabel: "Đã đóng",
      lineLabel: "Phải đóng",
    }));
  }, [tuitionReport, tuitionRows]);

  const classComboSeries = useMemo<ComboPoint[]>(() => {
    return classes.slice(0, 7).map((c) => ({
      label: c.name.length > 13 ? `${c.name.slice(0, 13)}…` : c.name,
      barValue: c.current_count,
      lineValue: c.capacity,
      tooltipTitle: `${c.name} (${c.site_code})`,
      barLabel: "Sĩ số hiện tại",
      lineLabel: "Sức chứa tối đa",
    }));
  }, [classes]);

  const activeComboConfig = useMemo(() => {
    if (comboMode === "finance") {
      return {
        points: financeComboSeries,
        barLegend: "Đã thu (VND)",
        lineLegend: "Phải thu (VND)",
        formatBarAxis: formatAxisCompact,
        formatBarValue: formatVnd,
        formatLineValue: formatVnd,
      };
    }
    if (comboMode === "classes") {
      return {
        points: classComboSeries,
        barLegend: "Sĩ số hiện tại",
        lineLegend: "Sức chứa tối đa",
        formatBarAxis: (v: number) => String(v),
        formatBarValue: (v: number) => `${v} học viên`,
        formatLineValue: (v: number) => `${v} chỗ`,
      };
    }
    return {
      points: dailyActivitySeries,
      barLegend: "Tổng nhật ký (dbo.Logs)",
      lineLegend: "Thao tác thành công",
      formatBarAxis: (v: number) => String(v),
      formatBarValue: (v: number) => `${v} lượt`,
      formatLineValue: (v: number) => `${v} lượt`,
    };
  }, [comboMode, dailyActivitySeries, financeComboSeries, classComboSeries]);

  const donutConfig = useMemo<{ segments: DonutSegment[]; centerValue: string; centerLabel: string }>(() => {
    if (donutMode === "classes") {
      const counts = {
        dang_hoc: classes.filter((c) => c.status === "dang_hoc").length,
        sap_mo: classes.filter((c) => c.status === "sap_mo").length,
        ket_thuc: classes.filter((c) => c.status === "ket_thuc").length,
        huy: classes.filter((c) => c.status === "huy").length,
      };
      return {
        segments: [
          { key: "dang_hoc", label: "Đang học", value: counts.dang_hoc, color: "#10b981" },
          { key: "sap_mo", label: "Sắp mở", value: counts.sap_mo, color: "#3b82f6" },
          { key: "ket_thuc", label: "Kết thúc", value: counts.ket_thuc, color: "#8b5cf6" },
          { key: "huy", label: "Đã hủy", value: counts.huy, color: "#94a3b8" },
        ],
        centerValue: String(classes.length),
        centerLabel: "Lớp học",
      };
    }
    return {
      segments: [
        { key: "collected", label: "Đã thu ròng", value: Math.max(0, netCollected), color: "#3b82f6" },
        { key: "outstanding", label: "Còn nợ", value: Math.max(0, outstanding), color: "#f59e0b" },
        ...(totalRefunded > 0 ? [{ key: "refunded", label: "Đã hoàn", value: totalRefunded, color: "#94a3b8" }] : []),
      ],
      centerValue: `${collectionRate}%`,
      centerLabel: "Tỷ lệ thu",
    };
  }, [donutMode, classes, netCollected, outstanding, totalRefunded, collectionRate]);

  // Real sparkline arrays derived from DB records
  const activitySpark = dailyActivitySeries.length >= 2
    ? dailyActivitySeries.map((d) => d.barValue)
    : [totalStudents, totalStudents];
  const studentSpark = (studentCounts?.results?.length ?? 0) >= 2
    ? studentCounts!.results.map((r) => r.active_students)
    : [Math.max(0, totalStudents), Math.max(0, totalStudents)];
  const paidSpark = tuitionRows.length >= 2
    ? tuitionRows.slice(0, 7).map((t) => t.amount_paid)
    : [0, netCollected];
  const classSpark = classes.length >= 2
    ? classes.slice(0, 7).map((c) => c.current_count)
    : [0, totalEnrolled];

  const scopeBadgeText = isAdminBig
    ? apiSiteParam
      ? `ADMIN BIG · Cơ sở ${apiSiteParam}`
      : `ADMIN BIG · GLOBAL (${activeSitesCount} site)`
    : `ADMIN SMALL · Cơ sở ${user?.site_code || "—"}`;

  return (
    <div className={styles.dashboardRoot}>
      {/* Top Greeting Header */}
      <header className={styles.greetingHeader}>
        <div className={styles.greetingLeft}>
          <h1>
            Xin chào, {user?.username || "Quản trị viên"} <span aria-hidden="true">👋</span>
          </h1>
          <p>
            <span>
              {isAdminBig
                ? "Tổng hợp dữ liệu phân tán theo thời gian thực từ các CSDL SQL Server."
                : `Số liệu cục bộ tại cơ sở ${user?.site_code || "được gán"}.`}
            </span>
          </p>
        </div>

        <div className={styles.greetingRight}>
          <span className={styles.scopePill}>
            <span className={studentCounts?.complete === false ? styles.warnDot : styles.liveDot} />
            {scopeBadgeText}
          </span>
          <button type="button" className={styles.refreshBtn} onClick={() => void loadDashboard()} disabled={loading}>
            <ReloadOutlined spin={loading} />
            Làm mới
          </button>
        </div>
      </header>

      {/* Distributed Completeness Warning */}
      {studentCounts && !studentCounts.complete && (
        <Alert
          type="warning"
          showIcon
          title="Dữ liệu phân tán chưa đầy đủ"
          description={`Các site chưa phản hồi: ${studentCounts.missing_sites.join(", ")}. Số liệu hiện tại chỉ tính từ các cơ sở đang hoạt động.`}
        />
      )}
      {errors.length > 0 && (
        <Alert type="warning" showIcon title="Một số nguồn dữ liệu gặp lỗi" description={errors.join(" · ")} />
      )}

      {loading && !studentCounts && !tuitionReport ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : (
        <>
          {/* Row 1: 4 Animated KPI Cards with Sparkline */}
          <section className={styles.kpiGrid} aria-label="Chỉ số tổng quan">
            <KpiSparkCard
              title="Học viên đang học"
              value={totalStudents}
              subtitle={`Tại ${activeSitesCount || 1} cơ sở hoạt động`}
              tone="blue"
              metaTone="info"
              icon={<TeamOutlined />}
              sparkPoints={activitySpark.length >= 2 ? activitySpark : studentSpark}
              delayMs={0}
            />
            <KpiSparkCard
              title="Học phí đã thu ròng"
              value={netCollected}
              valueFormatter={formatVnd}
              subtitle={`Đạt ${collectionRate}% trên ${formatVnd(totalDue)}`}
              tone="emerald"
              metaTone="up"
              icon={<DollarCircleOutlined />}
              sparkPoints={paidSpark}
              delayMs={70}
            />
            <KpiSparkCard
              title="Lớp học đang mở"
              value={activeClasses}
              valueFormatter={(v) => `${v} / ${classes.length} lớp`}
              subtitle={`Sĩ số ${totalEnrolled}/${totalCapacity} chỗ (${fillRate}%)`}
              tone="violet"
              metaTone="info"
              icon={<BookOutlined />}
              sparkPoints={classSpark}
              delayMs={140}
            />
            <KpiSparkCard
              title="Công nợ còn thu"
              value={outstanding}
              valueFormatter={formatVnd}
              subtitle={`${accountsWithBalance} khoản nợ · ${pendingTransfers} chờ chuyển`}
              tone="amber"
              metaTone={outstanding > 0 ? "warn" : "up"}
              icon={<WalletOutlined />}
              sparkPoints={activitySpark}
              delayMs={210}
            />
          </section>

          {/* Row 2: Combo Chart + Donut Chart + Recent Activity */}
          <section className={styles.middleGrid}>
            <div className={styles.panelCard} style={{ animationDelay: "120ms" }}>
              <div className={styles.panelHeader}>
                <h3 className={styles.panelTitle}>Phân tích dữ liệu</h3>
                <div className={styles.modeTabs} role="tablist" aria-label="Chế độ biểu đồ">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={comboMode === "activity"}
                    className={comboMode === "activity" ? styles.active : ""}
                    onClick={() => setComboMode("activity")}
                  >
                    Hoạt động
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={comboMode === "finance"}
                    className={comboMode === "finance" ? styles.active : ""}
                    onClick={() => setComboMode("finance")}
                  >
                    Tài chính
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={comboMode === "classes"}
                    className={comboMode === "classes" ? styles.active : ""}
                    onClick={() => setComboMode("classes")}
                  >
                    Lớp học
                  </button>
                </div>
              </div>

              <ComboBarLineChart {...activeComboConfig} />
            </div>

            <div className={styles.panelCard} style={{ animationDelay: "180ms" }}>
              <div className={styles.panelHeader}>
                <h3 className={styles.panelTitle}>
                  {donutMode === "tuition" ? "Tỷ lệ thu học phí" : "Tình trạng lớp học"}
                </h3>
                <div className={styles.modeTabs}>
                  <button
                    type="button"
                    className={donutMode === "tuition" ? styles.active : ""}
                    onClick={() => setDonutMode("tuition")}
                  >
                    Học phí
                  </button>
                  <button
                    type="button"
                    className={donutMode === "classes" ? styles.active : ""}
                    onClick={() => setDonutMode("classes")}
                  >
                    Lớp
                  </button>
                </div>
              </div>

              <DonutChartCard {...donutConfig} />
            </div>

            <RecentActivityCard logs={auditLogs} delayMs={240} />
          </section>

          {/* Row 3: Ranked Classes + Distributed Node Health */}
          <section className={styles.bottomGrid}>
            <TopClassesCard classes={classes} delayMs={280} />
            <DistributedClusterCard
              isAdminBig={isAdminBig}
              studentCounts={studentCounts}
              tuitionReport={tuitionReport}
              transfers={transfers}
              delayMs={320}
            />
          </section>
        </>
      )}
    </div>
  );
}

function StaffDashboard({ role, siteCode, username }: { role?: Role; siteCode: string | null; username?: string }) {
  const [classes, setClasses] = useState<ClassRow[]>([]);
  const [transfers, setTransfers] = useState<TransferRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      academicsApi.classes(undefined, { limit: 50 }),
      role && ["tu_van", "ke_toan"].includes(role) ? academicsApi.transfers() : Promise.resolve(null),
    ]).then(([clsRes, trRes]) => {
      if (!active) return;
      if (clsRes.status === "fulfilled" && clsRes.value) setClasses(clsRes.value.results || []);
      if (trRes.status === "fulfilled" && trRes.value) setTransfers(trRes.value.results || []);
      setLoading(false);
    });
    return () => { active = false; };
  }, [role]);

  const roleLabels: Record<string, string> = {
    tu_van: "Tư vấn & Xếp lớp",
    ke_toan: "Kế toán",
    le_tan: "Lễ tân",
  };

  const links: { label: string; href: string; roles: Role[]; icon: React.ReactNode }[] = [
    { label: "Hồ sơ học viên", href: "/admin/students", roles: ["tu_van", "ke_toan"], icon: <TeamOutlined /> },
    { label: "Lớp học & Xếp lớp", href: "/admin/classes", roles: ["le_tan", "tu_van", "ke_toan"], icon: <CalendarOutlined /> },
    { label: "Học phí & Thu tiền", href: "/admin/tuition", roles: ["ke_toan", "tu_van"], icon: <DollarCircleOutlined /> },
    { label: "Chuyển cơ sở", href: "/admin/transfers", roles: ["ke_toan", "tu_van"], icon: <SwapOutlined /> },
  ];

  const activeClasses = classes.filter((c) => c.status === "dang_hoc").length;
  const totalStudents = classes.reduce((s, c) => s + (c.current_count || 0), 0);

  return (
    <div className={styles.dashboardRoot}>
      <header className={styles.greetingHeader}>
        <div className={styles.greetingLeft}>
          <h1>Xin chào, {username || "Nhân viên"} 👋</h1>
          <p>Không gian làm việc · {role ? roleLabels[role] || role : "Nhân viên"} · Cơ sở {siteCode || "—"}</p>
        </div>
        <span className={styles.scopePill}>
          <span className={styles.liveDot} /> LOCAL · Site {siteCode || "—"}
        </span>
      </header>

      {loading ? (
        <Skeleton active paragraph={{ rows: 5 }} />
      ) : (
        <>
          <section className={styles.kpiGrid}>
            <KpiSparkCard
              title="Lớp đang giảng dạy"
              value={activeClasses}
              valueFormatter={(v) => `${v} / ${classes.length} lớp`}
              subtitle={`Tại cơ sở ${siteCode || "—"}`}
              tone="blue"
              icon={<BookOutlined />}
              sparkPoints={classes.slice(0, 6).map((c) => c.current_count)}
            />
            <KpiSparkCard
              title="Tổng lượt học viên trong lớp"
              value={totalStudents}
              subtitle="Theo sĩ số lớp hiện tại"
              tone="emerald"
              icon={<TeamOutlined />}
              sparkPoints={classes.slice(0, 6).map((c) => c.capacity)}
            />
            <KpiSparkCard
              title="Đề nghị chuyển cơ sở"
              value={transfers.filter((t) => t.status === "cho_duyet").length}
              valueFormatter={(v) => `${v} chờ duyệt`}
              subtitle={`Tổng ${transfers.length} hồ sơ`}
              tone="amber"
              icon={<SwapOutlined />}
              sparkPoints={[transfers.length, transfers.filter((t) => t.status === "cho_duyet").length]}
            />
          </section>

          <section className={styles.bottomGrid}>
            <TopClassesCard classes={classes} />
            <div className={styles.panelCard}>
              <div className={styles.panelHeader}>
                <h3 className={styles.panelTitle}>Nghiệp vụ được phân quyền</h3>
              </div>
              <div className={styles.quickActionsWrap}>
                {links
                  .filter((item) => role && item.roles.includes(role))
                  .map((item) => (
                    <Link key={item.href} href={item.href} className={styles.quickActionBtn}>
                      {item.icon}
                      {item.label}
                    </Link>
                  ))}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
