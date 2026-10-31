"use client";

import { useState } from "react";
import {
  FileTextOutlined,
} from "@ant-design/icons";
import styles from "../common/AdminPageCommon.module.scss";

type AuditLogItem = {
  id: string;
  timestamp: string;
  actionType: "DISTRIBUTED-TX" | "REPLICATED-WRITE" | "LOCAL" | "GLOBAL" | "AUTH";
  actor: string;
  siteScope: string;
  details: string;
  status: "SUCCESS" | "FAILED" | "WARN";
};

const INITIAL_LOGS: AuditLogItem[] = [
  {
    id: "1",
    timestamp: "30/10/2026 09:25:10",
    actionType: "DISTRIBUTED-TX",
    actor: "Quốc Hiếu (Admin Big)",
    siteScope: "Q1 ➔ Q7",
    details: "Duyệt giao dịch chuyển cơ sở TR-2026-0001 (HV Q1-HV-000102 sang Q7). 2PC Commit thành công.",
    status: "SUCCESS",
  },
  {
    id: "2",
    timestamp: "30/10/2026 09:05:40",
    actionType: "REPLICATED-WRITE",
    actor: "Quốc Hiếu (Admin Big)",
    siteScope: "Q1, Q7, TD",
    details: "Nhân bản môn học MH-TOEIC-700 sang 3 site CSDL. Idempotency ACK đã ghi vào dbo.Logs.",
    status: "SUCCESS",
  },
  {
    id: "3",
    timestamp: "30/10/2026 08:35:12",
    actionType: "LOCAL",
    actor: "Trần Văn Bình (Admin Small Q1)",
    siteScope: "Q1",
    details: "Ghi nhận phiếu thu Q1-PT-2026-0012 số tiền 4.500.000 đ cho học viên Q1-HV-000102.",
    status: "SUCCESS",
  },
  {
    id: "4",
    timestamp: "30/10/2026 08:15:00",
    actionType: "AUTH",
    actor: "quochieu_big",
    siteScope: "Hệ thống",
    details: "Đăng nhập thành công từ IP 172.24.16.1. Phiên làm việc cấp hạn 3600s.",
    status: "SUCCESS",
  },
  {
    id: "5",
    timestamp: "29/10/2026 16:45:22",
    actionType: "DISTRIBUTED-TX",
    actor: "Coordinator Service",
    siteScope: "TD ➔ Q1",
    details: "Thực thi TR-2026-0003 gặp lỗi mạng tạm thời tại đích Q1. Chờ trigger Forward Recovery Retry.",
    status: "WARN",
  },
];

export default function AuditPage() {
  const [logs] = useState<AuditLogItem[]>(INITIAL_LOGS);
  const [filterType, setFilterType] = useState<string>("ALL");

  const filteredLogs = logs.filter((l) => {
    if (filterType !== "ALL" && l.actionType !== filterType) return false;
    return true;
  });

  const renderTypeBadge = (type: AuditLogItem["actionType"]) => {
    switch (type) {
      case "DISTRIBUTED-TX":
        return <span className={`${styles.badge} ${styles.tx}`}>DISTRIBUTED-TX (2PC)</span>;
      case "REPLICATED-WRITE":
        return <span className={`${styles.badge} ${styles.replicate}`}>REPLICATED-WRITE</span>;
      case "LOCAL":
        return <span className={`${styles.badge} ${styles.site}`}>LOCAL</span>;
      case "GLOBAL":
        return <span className={`${styles.badge} ${styles.global}`}>GLOBAL</span>;
      case "AUTH":
        return <span className={`${styles.badge} ${styles.active}`}>AUTH</span>;
    }
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1>Nhật ký phân tán & Kiểm toán</h1>
            <span className={`${styles.badge} ${styles.site}`}>
              <FileTextOutlined /> Append-only Audit Trail
            </span>
          </div>
          <p className={styles.subtitle}>
            Ghi vết toàn bộ giao dịch phân tán, nhân bản dữ liệu và truy cập hệ thống. Tuyệt đối không ghi mật khẩu hay token vào nhật ký.
          </p>
        </div>
      </div>

      {/* Filter */}
      <div className={styles.filterCard}>
        <div className={styles.filterGroup}>
          <select
            className={styles.filterSelect}
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="ALL">Tất cả nghiệp vụ phân tán</option>
            <option value="DISTRIBUTED-TX">Giao dịch phân tán (DISTRIBUTED-TX)</option>
            <option value="REPLICATED-WRITE">Nhân bản dữ liệu (REPLICATED-WRITE)</option>
            <option value="LOCAL">Thao tác cơ sở cục bộ (LOCAL)</option>
            <option value="AUTH">Xác thực & Phiên (AUTH)</option>
          </select>
        </div>

        <span style={{ fontSize: "12.5px", color: "var(--admin-text-secondary)" }}>
          Bảo đảm tính toàn vẹn: Nhật ký lưu tại bảng <code>dbo.Logs</code> tại từng site
        </span>
      </div>

      {/* Table */}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Thời gian</th>
                <th>Phân loại nghiệp vụ</th>
                <th>Người thực hiện</th>
                <th>Phạm vi Site</th>
                <th>Chi tiết nhật ký kiểm toán</th>
                <th>Kết quả</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((l) => (
                <tr key={l.id}>
                  <td style={{ fontSize: "12px", color: "var(--admin-text-secondary)", whiteSpace: "nowrap" }}>
                    {l.timestamp}
                  </td>
                  <td>{renderTypeBadge(l.actionType)}</td>
                  <td style={{ fontWeight: 600 }}>{l.actor}</td>
                  <td>
                    <span className={`${styles.badge} ${styles.site}`}>{l.siteScope}</span>
                  </td>
                  <td>{l.details}</td>
                  <td>
                    {l.status === "SUCCESS" ? (
                      <span className={`${styles.badge} ${styles.active}`}>Thành công</span>
                    ) : (
                      <span className={`${styles.badge} ${styles.rejected}`}>Cảnh báo / Lỗi</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className={styles.tableFooter}>
          <span>Hiển thị {filteredLogs.length} bản ghi nhật ký phân tán</span>
          <span>Bảo vệ quyền riêng tư: Mật khẩu và token đã băm hoàn toàn trước khi lưu</span>
        </div>
      </div>
    </div>
  );
}

