"use client";

import { useState } from "react";
import {
  SwapOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import styles from "../common/AdminPageCommon.module.scss";

type TransferItem = {
  id: string;
  transferId: string;
  studentCode: string;
  studentName: string;
  sourceSite: "Q1" | "Q7" | "TD";
  targetSite: "Q1" | "Q7" | "TD";
  reason: string;
  status: "cho_duyet" | "da_duyet" | "thanh_cong" | "tu_choi" | "that_bai";
  requestDate: string;
  decidedBy?: string;
  coordinatorStep?: string;
};

const INITIAL_TRANSFERS: TransferItem[] = [
  {
    id: "1",
    transferId: "TR-2026-0001",
    studentCode: "Q1-HV-000102",
    studentName: "Nguyễn Văn An",
    sourceSite: "Q1",
    targetSite: "Q7",
    reason: "Chuyển nơi ở sang Quận 7 để tiện đi làm",
    status: "cho_duyet",
    requestDate: "28/10/2026 09:30",
    coordinatorStep: "Chờ Admin Big duyệt đề nghị",
  },
  {
    id: "2",
    transferId: "TR-2026-0002",
    studentCode: "Q7-HV-000089",
    studentName: "Trần Thị Mai",
    sourceSite: "Q7",
    targetSite: "TD",
    reason: "Chuyển chi nhánh học gần trường ĐH Bách Khoa Thủ Đức",
    status: "thanh_cong",
    requestDate: "27/10/2026 14:15",
    decidedBy: "Quốc Hiếu (Admin Big)",
    coordinatorStep: "2PC Commit hoàn tất 2 site (Q7 -> TD)",
  },
  {
    id: "3",
    transferId: "TR-2026-0003",
    studentCode: "TD-HV-000215",
    studentName: "Lê Hoàng Long",
    sourceSite: "TD",
    targetSite: "Q1",
    reason: "Đăng ký học ca tối tại cơ sở Quận 1",
    status: "that_bai",
    requestDate: "29/10/2026 16:45",
    decidedBy: "Quốc Hiếu (Admin Big)",
    coordinatorStep: "Mất kết nối mạng tại đích -> Cần chạy Retry phục hồi tiến về phía trước",
  },
];

export default function TransfersPage() {
  const [transfers, setTransfers] = useState<TransferItem[]>(INITIAL_TRANSFERS);
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);
  const [newRequest, setNewRequest] = useState({
    studentCode: "",
    studentName: "",
    sourceSite: "Q1",
    targetSite: "Q7",
    reason: "",
  });

  const filteredTransfers = transfers.filter((t) => {
    if (selectedStatus !== "ALL" && t.status !== selectedStatus) return false;
    return true;
  });

  const handleApprove = (id: string) => {
    setTransfers(
      transfers.map((t) =>
        t.id === id
          ? {
              ...t,
              status: "thanh_cong",
              decidedBy: "Quốc Hiếu (Admin Big)",
              coordinatorStep: `Coordinator đã ghi nhận commit: ${t.targetSite} tạo mới hồ sơ dang_hoc, ${t.sourceSite} cập nhật da_chuyen_di.`,
            }
          : t
      )
    );
  };

  const handleReject = (id: string) => {
    setTransfers(
      transfers.map((t) =>
        t.id === id
          ? {
              ...t,
              status: "tu_choi",
              decidedBy: "Quốc Hiếu (Admin Big)",
              coordinatorStep: "Từ chối đề nghị. Hồ sơ giữ nguyên tại cơ sở nguồn.",
            }
          : t
      )
    );
  };

  const handleRetry = (id: string) => {
    setTransfers(
      transfers.map((t) =>
        t.id === id
          ? {
              ...t,
              status: "thanh_cong",
              coordinatorStep: "Thử lại Forward Recovery thành công: Đích đã ghi nhận và nguồn hoàn tất chuyển.",
            }
          : t
      )
    );
  };

  const handleCreateRequest = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRequest.studentCode.trim() || !newRequest.studentName.trim()) return;

    const created: TransferItem = {
      id: Date.now().toString(),
      transferId: `TR-2026-000${transfers.length + 1}`,
      studentCode: newRequest.studentCode.trim(),
      studentName: newRequest.studentName.trim(),
      sourceSite: newRequest.sourceSite as "Q1" | "Q7" | "TD",
      targetSite: newRequest.targetSite as "Q1" | "Q7" | "TD",
      reason: newRequest.reason.trim() || "Chuyển cơ sở theo nguyện vọng",
      status: "cho_duyet",
      requestDate: new Date().toLocaleString("vi-VN"),
      coordinatorStep: "Đề nghị LOCAL đã lưu tại CSDL nguồn -> Chờ Admin Big duyệt",
    };

    setTransfers([created, ...transfers]);
    setIsRequestModalOpen(false);
    setNewRequest({
      studentCode: "",
      studentName: "",
      sourceSite: "Q1",
      targetSite: "Q7",
      reason: "",
    });
  };

  const renderStatusBadge = (status: TransferItem["status"]) => {
    switch (status) {
      case "cho_duyet":
        return <span className={`${styles.badge} ${styles.pending}`}>Chờ duyệt</span>;
      case "thanh_cong":
        return <span className={`${styles.badge} ${styles.active}`}>✓ Thành công (2PC)</span>;
      case "tu_choi":
        return <span className={`${styles.badge} ${styles.rejected}`}>Đã từ chối</span>;
      case "that_bai":
        return <span className={`${styles.badge} ${styles.rejected}`}>⚠ Lỗi phân tán (Cần Retry)</span>;
      default:
        return <span className={`${styles.badge} ${styles.site}`}>{status}</span>;
    }
  };

  return (
    <div className={styles.pageContainer}>
      {/* Header */}
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1>Giao dịch chuyển cơ sở</h1>
            <span className={`${styles.badge} ${styles.tx}`}>
              <SafetyCertificateOutlined /> Distributed Transaction (Coordinator / 2PC)
            </span>
          </div>
          <p className={styles.subtitle}>
            Điều phối giao dịch giữa CSDL nguồn và CSDL đích theo quy trình 3 chặng nghiêm ngặt.
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            type="button"
            className={`${styles.btn} ${styles.primary}`}
            onClick={() => setIsRequestModalOpen(true)}
          >
            <PlusOutlined /> Tạo đề nghị chuyển cơ sở (LOCAL)
          </button>
        </div>
      </div>

      {/* 2PC Architecture Notice */}
      <div
        style={{
          background: "var(--admin-card-bg)",
          border: "1px solid var(--admin-border)",
          borderLeft: "4px solid #f59e0b",
          borderRadius: "var(--admin-radius, 10px)",
          padding: "14px 18px",
          fontSize: "13px",
          display: "flex",
          flexDirection: "column",
          gap: "4px",
        }}
      >
        <strong style={{ color: "var(--admin-text)" }}>
          Cơ chế điều phối giao dịch phân tán (Coordinator Model):
        </strong>
        <span style={{ color: "var(--admin-text-secondary)" }}>
          Chặng 1: Admin Small tạo đề nghị <code>LOCAL</code> tại CSDL nguồn → Chặng 2: Admin Big duyệt qua Global Inbox → Chặng 3: Coordinator thực thi <code>DISTRIBUTED-TX</code> (ghi đích trước, cập nhật nguồn <code>da_chuyen_di</code>, phục hồi tiến về phía trước nếu mạng chập chờn).
        </span>
      </div>

      {/* Filters */}
      <div className={styles.filterCard}>
        <div className={styles.filterGroup}>
          <select
            className={styles.filterSelect}
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
          >
            <option value="ALL">Tất cả trạng thái giao dịch</option>
            <option value="cho_duyet">Chờ duyệt (Pending Approval)</option>
            <option value="thanh_cong">Thành công (Committed)</option>
            <option value="that_bai">Lỗi gián đoạn mạng (Pending Retry)</option>
            <option value="tu_choi">Đã từ chối (Rejected)</option>
          </select>
        </div>

        <span style={{ fontSize: "12.5px", color: "var(--admin-text-muted)" }}>
          Hộp thư Admin Big: Đọc qua Global Query từ 3 site CSDL
        </span>
      </div>

      {/* Table */}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Mã GD</th>
                <th>Mã học viên</th>
                <th>Họ tên</th>
                <th>Site nguồn ➔ Site đích</th>
                <th>Lý do</th>
                <th>Trạng thái 2PC</th>
                <th>Tiến trình Coordinator</th>
                <th>Thời gian</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {filteredTransfers.map((t) => (
                <tr key={t.id}>
                  <td>
                    <span className={styles.codeCell}>{t.transferId}</span>
                  </td>
                  <td>
                    <span className={styles.codeCell}>{t.studentCode}</span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{t.studentName}</td>
                  <td>
                    <span className={`${styles.badge} ${styles.site}`}>{t.sourceSite}</span>
                    {" ➔ "}
                    <span className={`${styles.badge} ${styles.global}`}>{t.targetSite}</span>
                  </td>
                  <td style={{ maxWidth: "200px" }}>{t.reason}</td>
                  <td>{renderStatusBadge(t.status)}</td>
                  <td style={{ fontSize: "12px", color: "var(--admin-text-secondary)" }}>
                    {t.coordinatorStep}
                  </td>
                  <td style={{ fontSize: "12px", color: "var(--admin-text-muted)" }}>
                    {t.requestDate}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: "6px" }}>
                      {t.status === "cho_duyet" && (
                        <>
                          <button
                            type="button"
                            className={`${styles.btn} ${styles.sm} ${styles.primary}`}
                            title="Duyệt chuyển cơ sở (Chạy giao dịch Coordinator)"
                            onClick={() => handleApprove(t.id)}
                          >
                            <CheckCircleOutlined /> Duyệt
                          </button>
                          <button
                            type="button"
                            className={`${styles.btn} ${styles.sm} ${styles.danger}`}
                            title="Từ chối đề nghị"
                            onClick={() => handleReject(t.id)}
                          >
                            <CloseCircleOutlined /> Từ chối
                          </button>
                        </>
                      )}

                      {t.status === "that_bai" && (
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.sm}`}
                          style={{ borderColor: "#f59e0b", color: "#f59e0b" }}
                          title="Thực hiện Forward Recovery Retry"
                          onClick={() => handleRetry(t.id)}
                        >
                          <SyncOutlined /> Retry (Phục hồi)
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className={styles.tableFooter}>
          <span>Hệ thống bảo toàn lịch sử: Hồ sơ cũ tại site nguồn được giữ lại với trạng thái <code>da_chuyen_di</code>.</span>
          <span>Bảo đảm không tạo học viên trùng lặp xuyên CSDL</span>
        </div>
      </div>

      {/* Modal đề nghị chuyển cơ sở */}
      {isRequestModalOpen && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <h3>Tạo đề nghị chuyển cơ sở (LOCAL Proposal)</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setIsRequestModalOpen(false)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateRequest}>
              <div className={styles.modalBody}>
                <div className={styles.formGroup}>
                  <label>Mã học viên (*)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: Q1-HV-000102"
                    value={newRequest.studentCode}
                    onChange={(e) => setNewRequest({ ...newRequest, studentCode: e.target.value })}
                    required
                  />
                </div>

                <div className={styles.formGroup}>
                  <label>Họ và tên học viên (*)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: Nguyễn Văn An"
                    value={newRequest.studentName}
                    onChange={(e) => setNewRequest({ ...newRequest, studentName: e.target.value })}
                    required
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div className={styles.formGroup}>
                    <label>Cơ sở nguồn (*)</label>
                    <select
                      value={newRequest.sourceSite}
                      onChange={(e) => setNewRequest({ ...newRequest, sourceSite: e.target.value })}
                    >
                      <option value="Q1">Quận 1 (Q1)</option>
                      <option value="Q7">Quận 7 (Q7)</option>
                      <option value="TD">Thủ Đức (TD)</option>
                    </select>
                  </div>

                  <div className={styles.formGroup}>
                    <label>Cơ sở đích (*)</label>
                    <select
                      value={newRequest.targetSite}
                      onChange={(e) => setNewRequest({ ...newRequest, targetSite: e.target.value })}
                    >
                      <option value="Q7">Quận 7 (Q7)</option>
                      <option value="Q1">Quận 1 (Q1)</option>
                      <option value="TD">Thủ Đức (TD)</option>
                    </select>
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label>Lý do xin chuyển cơ sở (*)</label>
                  <textarea
                    rows={3}
                    placeholder="Nêu rõ lý do để Admin Big xem xét duyệt..."
                    value={newRequest.reason}
                    onChange={(e) => setNewRequest({ ...newRequest, reason: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className={styles.modalFooter}>
                <button
                  type="button"
                  className={styles.btn}
                  onClick={() => setIsRequestModalOpen(false)}
                >
                  Hủy
                </button>
                <button type="submit" className={`${styles.btn} ${styles.primary}`}>
                  Gửi đề nghị (Lưu CSDL nguồn)
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

