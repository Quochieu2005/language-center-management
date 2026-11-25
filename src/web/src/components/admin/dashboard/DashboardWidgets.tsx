"use client";

import Link from "next/link";
import {
  CheckCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  LoginOutlined,
  RightOutlined,
  SwapOutlined,
  SyncOutlined,
  TeamOutlined,
  TrophyOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Tag } from "antd";
import type { ClassRow, TransferRow } from "@/lib/api/academics";
import type { AdminAuditLog, SiteCounts, TuitionFinancialReport } from "@/lib/api/admin";
import styles from "./AdminDashboard.module.scss";

function formatRelativeTime(iso: string): string {
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return iso.slice(0, 10);
  const diffSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (diffSec < 60) return "Vừa xong";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} phút trước`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} giờ trước`;
  return `${Math.floor(diffSec / 86400)} ngày trước`;
}

function actionLabel(log: AdminAuditLog): { title: string; tone: "login" | "system" | "sync" | "warning" } {
  const act = (log.action || "").toLowerCase();
  if (log.result === "that_bai") {
    return { title: `Thao tác thất bại (${log.action || log.log_type})`, tone: "warning" };
  }
  if (log.log_type === "login" || act.includes("dang_nhap")) {
    return { title: "Đăng nhập hệ thống", tone: "login" };
  }
  if (log.log_type === "sync" || act.includes("dong_bo")) {
    return { title: `Đồng bộ dữ liệu ${log.destination_site ? `→ ${log.destination_site}` : ""}`, tone: "sync" };
  }
  if (act.includes("diem_danh")) return { title: "Điểm danh buổi học", tone: "system" };
  if (act.includes("diem")) return { title: "Cập nhật bảng điểm", tone: "system" };
  if (act.includes("hoc_phi") || act.includes("phieu")) return { title: "Ghi nhận học phí", tone: "system" };
  if (act.includes("dang_ky") || act.includes("lop")) return { title: "Xếp lớp & Ghi danh", tone: "system" };
  if (act.includes("chuyen")) return { title: "Điều phối chuyển cơ sở", tone: "sync" };
  if (log.affected_table) return { title: `Cập nhật ${log.affected_table}`, tone: "system" };
  return { title: log.action || "Hoạt động hệ thống", tone: "system" };
}

export function RecentActivityCard({
  logs,
  delayMs = 200,
}: {
  logs: AdminAuditLog[];
  delayMs?: number;
}) {
  return (
    <div className={styles.panelCard} style={{ animationDelay: `${delayMs}ms` }}>
      <div className={styles.panelHeader}>
        <h3 className={styles.panelTitle}>Hoạt động gần đây</h3>
        <Link href="/admin/audit" className={styles.panelLink}>
          Xem tất cả <RightOutlined style={{ fontSize: 10 }} />
        </Link>
      </div>

      {logs.length === 0 ? (
        <div style={{ color: "var(--admin-text-muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
          Chưa ghi nhận nhật ký hoạt động nào.
        </div>
      ) : (
        <div className={styles.activityList}>
          {logs.slice(0, 5).map((log) => {
            const { title, tone } = actionLabel(log);
            return (
              <div className={styles.activityItem} key={`${log.site_code}-${log.log_id}`}>
                <div className={styles.actLeft}>
                  <div className={`${styles.actIcon} ${styles[tone]}`}>
                    {tone === "login" && <LoginOutlined />}
                    {tone === "system" && <CheckCircleOutlined />}
                    {tone === "sync" && <SyncOutlined />}
                    {tone === "warning" && <WarningOutlined />}
                  </div>
                  <div className={styles.actContent}>
                    <div className={styles.actTitle} title={title}>
                      {title}
                    </div>
                    <div className={styles.actSub}>
                      Site {log.site_code}
                      {log.record_id ? ` · ${log.record_id}` : log.account_id ? ` · ${log.account_id}` : ""}
                    </div>
                  </div>
                </div>
                <span className={styles.actTime}>{formatRelativeTime(log.occurred_at)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function TopClassesCard({
  classes,
  delayMs = 260,
}: {
  classes: ClassRow[];
  delayMs?: number;
}) {
  const ranked = [...classes]
    .sort((a, b) => (b.current_count ?? 0) - (a.current_count ?? 0))
    .slice(0, 4);

  return (
    <div className={styles.panelCard} style={{ animationDelay: `${delayMs}ms` }}>
      <div className={styles.panelHeader}>
        <h3 className={styles.panelTitle}>
          <TrophyOutlined style={{ color: "#f59e0b" }} /> Lớp học nổi bật theo sĩ số
        </h3>
        <Link href="/admin/classes" className={styles.panelLink}>
          Xem thêm <RightOutlined style={{ fontSize: 10 }} />
        </Link>
      </div>

      {ranked.length === 0 ? (
        <div style={{ color: "var(--admin-text-muted)", fontSize: 13, padding: "24px 0", textAlign: "center" }}>
          Chưa có lớp học nào trong cơ sở đang chọn.
        </div>
      ) : (
        <div className={styles.rankList}>
          {ranked.map((cls, idx) => {
            const cap = Math.max(1, cls.capacity || 1);
            const cur = cls.current_count || 0;
            const fillPct = Math.min(100, Math.round((cur / cap) * 100));
            const rankClass = idx === 0 ? styles.top1 : idx === 1 ? styles.top2 : idx === 2 ? styles.top3 : "";

            return (
              <div className={styles.rankItem} key={`${cls.site_code}-${cls.class_id}`}>
                <span className={`${styles.rankNum} ${rankClass}`}>{idx + 1}</span>
                <div className={styles.rankInfo}>
                  <div className={styles.rankName} title={cls.name}>
                    {cls.name}
                  </div>
                  <div className={styles.rankSub}>
                    {cls.course_name} · GV: {cls.teacher_name || "Chưa gán"} · Site {cls.site_code}
                  </div>
                </div>
                <div className={styles.rankMetrics}>
                  <div className={styles.rankStat}>
                    {cur}/{cap} HV ({fillPct}%)
                  </div>
                  <div className={styles.rankBarTrack}>
                    <div className={styles.rankBarFill} style={{ width: `${fillPct}%` }} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function DistributedClusterCard({
  isAdminBig,
  studentCounts,
  tuitionReport,
  transfers,
  delayMs = 320,
}: {
  isAdminBig: boolean;
  studentCounts: SiteCounts | null;
  tuitionReport: TuitionFinancialReport | null;
  transfers: TransferRow[];
  delayMs?: number;
}) {
  const activeSites = studentCounts?.site_codes ?? [];
  const missingSites = studentCounts?.missing_sites ?? [];
  const pendingTransfers = transfers.filter((t) => t.status === "cho_duyet").length;

  const tuitionBySite = new Map(
    (tuitionReport?.results ?? []).map((r) => [r.site_code, r]),
  );
  const studentsBySite = new Map(
    (studentCounts?.results ?? []).map((r) => [r.site_code, r.active_students]),
  );

  const quickLinks = [
    { label: "Học viên", href: "/admin/students", icon: <TeamOutlined /> },
    { label: "Lớp & Xếp lớp", href: "/admin/classes", icon: <DatabaseOutlined /> },
    { label: "Học phí", href: "/admin/tuition", icon: <CheckCircleOutlined /> },
    { label: `Chuyển cơ sở${pendingTransfers > 0 ? ` (${pendingTransfers})` : ""}`, href: "/admin/transfers", icon: <SwapOutlined /> },
  ];

  return (
    <div className={styles.panelCard} style={{ animationDelay: `${delayMs}ms` }}>
      <div className={styles.panelHeader}>
        <h3 className={styles.panelTitle}>
          <CloudServerOutlined style={{ color: "#3b82f6" }} /> Tình trạng CSDL Phân tán
        </h3>
        <Tag color={studentCounts?.complete === false ? "warning" : "success"} style={{ margin: 0 }}>
          {studentCounts?.complete === false ? "Thiếu phản hồi site" : isAdminBig ? "GLOBAL Đồng bộ" : "LOCAL Site Ready"}
        </Tag>
      </div>

      <div className={styles.clusterHero}>
        <div className={styles.nodeGrid}>
          {activeSites.map((site) => {
            const stCount = studentsBySite.get(site) ?? 0;
            const fin = tuitionBySite.get(site);
            return (
              <div className={styles.nodeBox} key={site}>
                <div className={styles.nodeTop}>
                  <span>Site {site}</span>
                  <Tag color="green" style={{ margin: 0, fontSize: 10, padding: "0 5px" }}>
                    Online
                  </Tag>
                </div>
                <div className={styles.nodeVal}>{stCount} HV</div>
                <div className={styles.nodeLbl}>
                  {fin
                    ? `Thu ròng ${new Intl.NumberFormat("vi-VN").format(fin.net_collected)} đ`
                    : "CSDL SQL Server riêng"}
                </div>
              </div>
            );
          })}

          {missingSites.map((site) => (
            <div className={styles.nodeBox} key={`miss-${site}`} style={{ borderColor: "#f59e0b" }}>
              <div className={styles.nodeTop}>
                <span>Site {site}</span>
                <Tag color="warning" style={{ margin: 0, fontSize: 10, padding: "0 5px" }}>
                  Offline
                </Tag>
              </div>
              <div className={styles.nodeVal} style={{ color: "#f59e0b" }}>—</div>
              <div className={styles.nodeLbl}>Chưa phản hồi</div>
            </div>
          ))}
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--admin-text-secondary)", marginBottom: 8 }}>
            Điều hướng nhanh nghiệp vụ
          </div>
          <div className={styles.quickActionsWrap}>
            {quickLinks.map((lnk) => (
              <Link className={styles.quickActionBtn} href={lnk.href} key={lnk.href}>
                {lnk.icon}
                {lnk.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
