"use client";

import { useState } from "react";
import {
  DollarCircleOutlined,
  PlusOutlined,
  PrinterOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import styles from "../common/AdminPageCommon.module.scss";

type TuitionRecord = {
  id: string;
  receiptCode: string;
  studentCode: string;
  studentName: string;
  site: "Q1" | "Q7" | "TD";
  className: string;
  amount: number;
  paidAmount: number;
  status: "da_dong_du" | "con_no" | "chua_dong";
  dueDate: string;
  paymentDate?: string;
};

const INITIAL_TUITION: TuitionRecord[] = [
  {
    id: "1",
    receiptCode: "Q1-PT-2026-0012",
    studentCode: "Q1-HV-000102",
    studentName: "Nguyễn Văn An",
    site: "Q1",
    className: "TOEIC Đột Phá 700+",
    amount: 4500000,
    paidAmount: 4500000,
    status: "da_dong_du",
    dueDate: "20/10/2026",
    paymentDate: "15/10/2026 10:20",
  },
  {
    id: "2",
    receiptCode: "Q7-PT-2026-0008",
    studentCode: "Q7-HV-000089",
    studentName: "Trần Thị Mai",
    site: "Q7",
    className: "IELTS Intensive 6.5",
    amount: 6800000,
    paidAmount: 3400000,
    status: "con_no",
    dueDate: "05/11/2026",
    paymentDate: "20/10/2026 15:40",
  },
  {
    id: "3",
    receiptCode: "TD-PT-2026-0015",
    studentCode: "TD-HV-000215",
    studentName: "Lê Hoàng Long",
    site: "TD",
    className: "Giao Tiếp Phản Xạ Quốc Tế",
    amount: 3200000,
    paidAmount: 0,
    status: "chua_dong",
    dueDate: "30/10/2026",
  },
];

export default function TuitionPage() {
  const [tuitionList, setTuitionList] = useState<TuitionRecord[]>(INITIAL_TUITION);
  const [selectedSite, setSelectedSite] = useState<string>("ALL");
  const [isCollectModalOpen, setIsCollectModalOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<TuitionRecord | null>(null);

  const filteredTuition = tuitionList.filter((t) => {
    if (selectedSite !== "ALL" && t.site !== selectedSite) return false;
    return true;
  });

  const handleOpenCollect = (t: TuitionRecord) => {
    setSelectedRecord(t);
    setIsCollectModalOpen(true);
  };

  const handleCollectPayment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRecord) return;

    setTuitionList(
      tuitionList.map((t) =>
        t.id === selectedRecord.id
          ? {
              ...t,
              paidAmount: t.amount,
              status: "da_dong_du",
              paymentDate: new Date().toLocaleString("vi-VN"),
            }
          : t
      )
    );
    setIsCollectModalOpen(false);
    setSelectedRecord(null);
  };

  const renderStatus = (status: TuitionRecord["status"]) => {
    switch (status) {
      case "da_dong_du":
        return <span className={`${styles.badge} ${styles.active}`}>Đã hoàn tất</span>;
      case "con_no":
        return <span className={`${styles.badge} ${styles.pending}`}>Còn nợ đợt 2</span>;
      case "chua_dong":
        return <span className={`${styles.badge} ${styles.rejected}`}>Chưa nộp</span>;
    }
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1>Học phí & Phiếu thu</h1>
            <span className={`${styles.badge} ${styles.site}`}>
              <DollarCircleOutlined /> Nghiệp vụ cục bộ (LOCAL Write)
            </span>
          </div>
          <p className={styles.subtitle}>
            Thu học phí tại quầy, tạo phiếu thu và lưu trữ tại CSDL SQL Server của từng cơ sở. Phiếu đã thu không được phép xóa.
          </p>
        </div>
      </div>

      {/* Filter */}
      <div className={styles.filterCard}>
        <div className={styles.filterGroup}>
          <select
            className={styles.filterSelect}
            value={selectedSite}
            onChange={(e) => setSelectedSite(e.target.value)}
          >
            <option value="ALL">Tất cả cơ sở</option>
            <option value="Q1">Cơ sở Quận 1 (QLTTNN_Q1)</option>
            <option value="Q7">Cơ sở Quận 7 (QLTTNN_Q7)</option>
            <option value="TD">Cơ sở Thủ Đức (QLTTNN_TD)</option>
          </select>
        </div>

        <span style={{ fontSize: "12.5px", color: "var(--admin-text-secondary)" }}>
          Quy tắc kiểm soát: Không gộp dữ liệu học phí giữa các CSDL xuyên site
        </span>
      </div>

      {/* Table */}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Mã biên nhận / Phiếu</th>
                <th>Mã học viên</th>
                <th>Họ và tên</th>
                <th>Cơ sở</th>
                <th>Khóa học</th>
                <th>Học phí chuẩn</th>
                <th>Đã thanh toán</th>
                <th>Hạn nộp</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {filteredTuition.map((t) => (
                <tr key={t.id}>
                  <td>
                    <span className={styles.codeCell}>{t.receiptCode}</span>
                  </td>
                  <td>
                    <span className={styles.codeCell}>{t.studentCode}</span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{t.studentName}</td>
                  <td>
                    <span className={`${styles.badge} ${styles.site}`}>{t.site}</span>
                  </td>
                  <td>{t.className}</td>
                  <td style={{ fontWeight: 600 }}>
                    {t.amount.toLocaleString("vi-VN")} đ
                  </td>
                  <td style={{ color: t.paidAmount === t.amount ? "#10b981" : "#f59e0b", fontWeight: 600 }}>
                    {t.paidAmount.toLocaleString("vi-VN")} đ
                  </td>
                  <td style={{ fontSize: "12px", color: "var(--admin-text-secondary)" }}>{t.dueDate}</td>
                  <td>{renderStatus(t.status)}</td>
                  <td>
                    <div style={{ display: "flex", gap: "6px" }}>
                      {t.status !== "da_dong_du" ? (
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.sm} ${styles.primary}`}
                          title="Thu tiền tại quầy"
                          onClick={() => handleOpenCollect(t)}
                        >
                          <PlusOutlined /> Thu tiền
                        </button>
                      ) : (
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.sm}`}
                          title="In phiếu thu"
                        >
                          <PrinterOutlined /> In phiếu
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
          <span>Tổng số khoản thu: {filteredTuition.length}</span>
          <span>Bảo mật tài chính: Chỉ kế toán và Admin có quyền ghi nhận phiếu thu</span>
        </div>
      </div>

      {/* Modal Thu tiền tại quầy */}
      {isCollectModalOpen && selectedRecord && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <h3>Ghi nhận thu tiền tại quầy (LOCAL)</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setIsCollectModalOpen(false)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCollectPayment}>
              <div className={styles.modalBody}>
                <div style={{ fontSize: "13px", display: "flex", flexDirection: "column", gap: "6px" }}>
                  <div>Học viên: <strong>{selectedRecord.studentName} ({selectedRecord.studentCode})</strong></div>
                  <div>Cơ sở thu: <strong>{selectedRecord.site}</strong></div>
                  <div>Khóa học: <strong>{selectedRecord.className}</strong></div>
                  <div>Số tiền còn nợ: <strong style={{ color: "#ef4444" }}>{(selectedRecord.amount - selectedRecord.paidAmount).toLocaleString("vi-VN")} đ</strong></div>
                </div>

                <div className={styles.formGroup} style={{ marginTop: "12px" }}>
                  <label>Phương thức thu tiền (*)</label>
                  <select defaultValue="tien_mat">
                    <option value="tien_mat">Tiền mặt tại quầy</option>
                    <option value="chuyen_khoan">Chuyển khoản ngân hàng trung tâm</option>
                    <option value="pos">Quẹt thẻ POS cơ sở</option>
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label>Ghi chú biên nhận</label>
                  <input type="text" placeholder="Ghi nhận nộp đủ đợt 2" />
                </div>
              </div>

              <div className={styles.modalFooter}>
                <button
                  type="button"
                  className={styles.btn}
                  onClick={() => setIsCollectModalOpen(false)}
                >
                  Hủy
                </button>
                <button type="submit" className={`${styles.btn} ${styles.primary}`}>
                  <CheckCircleOutlined /> Xác nhận xuất phiếu thu
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

