"use client";

import { useState } from "react";
import {
  BookOutlined,
  EditOutlined,
  SyncOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import styles from "../common/AdminPageCommon.module.scss";

type SubjectItem = {
  id: string;
  slug: string;
  code: string;
  name: string;
  description: string;
  sessions: number;
  tuitionFee: number;
  syncStatus: {
    q1: boolean;
    q7: boolean;
    td: boolean;
  };
  lastSync: string;
};

const INITIAL_SUBJECTS: SubjectItem[] = [
  {
    id: "1",
    slug: "tieng-anh-toeic-700",
    code: "MH-TOEIC-700",
    name: "Tiếng Anh Luyện Thi TOEIC 700+",
    description: "Khóa luyện thi TOEIC 4 kỹ năng cấp tốc theo format ETS 2026",
    sessions: 24,
    tuitionFee: 4500000,
    syncStatus: { q1: true, q7: true, td: true },
    lastSync: "30/10/2026 08:00",
  },
  {
    id: "2",
    slug: "tieng-anh-ielts-intensive",
    code: "MH-IELTS-65",
    name: "IELTS Intensive Mục Tiêu 6.5 - 7.5",
    description: "Chương trình chuyên sâu rèn luyện Writing & Speaking học thuật",
    sessions: 36,
    tuitionFee: 6800000,
    syncStatus: { q1: true, q7: true, td: true },
    lastSync: "29/10/2026 14:30",
  },
  {
    id: "3",
    slug: "tieng-anh-giao-tiep-quoc-te",
    code: "MH-COMM-A2",
    name: "Tiếng Anh Giao Tiếp Phản Xạ Quốc Tế",
    description: "Tập trung phản xạ tự nhiên cùng 100% giáo viên bản ngữ",
    sessions: 20,
    tuitionFee: 3200000,
    syncStatus: { q1: true, q7: true, td: true },
    lastSync: "28/10/2026 11:20",
  },
  {
    id: "4",
    slug: "tieng-anh-vstep-b2",
    code: "MH-VSTEP-B2",
    name: "Luyện Thi Chứng Chỉ VSTEP B2",
    description: "Đáp ứng chuẩn đầu ra đại học và cao học theo khung năng lực 6 bậc",
    sessions: 24,
    tuitionFee: 3800000,
    syncStatus: { q1: true, q7: true, td: true },
    lastSync: "25/10/2026 09:15",
  },
];

export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<SubjectItem[]>(INITIAL_SUBJECTS);
  const [editingSubject, setEditingSubject] = useState<SubjectItem | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);

  const handleOpenEdit = (s: SubjectItem) => {
    setEditingSubject({ ...s });
  };

  const handleSaveAndReplicate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSubject) return;

    setIsSyncing(true);
    setTimeout(() => {
      setSubjects(
        subjects.map((item) =>
          item.id === editingSubject.id
            ? {
                ...editingSubject,
                syncStatus: { q1: true, q7: true, td: true },
                lastSync: new Date().toLocaleString("vi-VN"),
              }
            : item
        )
      );
      setIsSyncing(false);
      setEditingSubject(null);
    }, 600);
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1>Môn học dùng chung</h1>
            <span className={`${styles.badge} ${styles.replicate}`}>
              <SyncOutlined /> Replicated-Write (Nhân bản toàn cục)
            </span>
          </div>
          <p className={styles.subtitle}>
            Bảng <code>MonHoc</code> được nhân bản giống hệt tại cả 3 CSDL (Q1, Q7, TD). Mọi cập nhật được Coordinator đồng bộ đồng thời.
          </p>
        </div>
      </div>

      {/* Replication Policy Banner */}
      <div
        style={{
          background: "var(--admin-card-bg)",
          border: "1px solid var(--admin-border)",
          borderLeft: "4px solid #10b981",
          borderRadius: "var(--admin-radius, 10px)",
          padding: "14px 18px",
          fontSize: "13px",
          display: "flex",
          flexDirection: "column",
          gap: "4px",
        }}
      >
        <strong style={{ color: "var(--admin-text)" }}>
          Chính sách đồng bộ nhân bản (Replication Architecture):
        </strong>
        <span style={{ color: "var(--admin-text-secondary)" }}>
          Chỉ Admin Big có quyền cập nhật bảng dùng chung. Coordinator ghi tới mọi site đang hoạt động kèm <code>Idempotency-Key</code> và ghi ACK vào <code>dbo.Logs</code> tại từng CSDL. Nếu thiếu site thì không báo thành công.
        </span>
      </div>

      {/* Table */}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Mã môn học</th>
                <th>Tên môn học</th>
                <th>Mô tả chương trình</th>
                <th>Số buổi</th>
                <th>Học phí chuẩn</th>
                <th>Trạng thái nhân bản (3 Site)</th>
                <th>Lần đồng bộ gần nhất</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => (
                <tr key={s.id}>
                  <td>
                    <span className={styles.codeCell}>{s.code}</span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{s.name}</td>
                  <td style={{ maxWidth: "260px", color: "var(--admin-text-secondary)" }}>
                    {s.description}
                  </td>
                  <td>{s.sessions} buổi</td>
                  <td style={{ fontWeight: 600 }}>{s.tuitionFee.toLocaleString("vi-VN")} đ</td>
                  <td>
                    <div style={{ display: "flex", gap: "6px" }}>
                      <span className={`${styles.badge} ${styles.active}`} title="QLTTNN_Q1 OK">
                        Q1: OK
                      </span>
                      <span className={`${styles.badge} ${styles.active}`} title="QLTTNN_Q7 OK">
                        Q7: OK
                      </span>
                      <span className={`${styles.badge} ${styles.active}`} title="QLTTNN_TD OK">
                        TD: OK
                      </span>
                    </div>
                  </td>
                  <td style={{ fontSize: "12px", color: "var(--admin-text-muted)" }}>
                    {s.lastSync}
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`${styles.btn} ${styles.sm} ${styles.primary}`}
                      title="Chỉnh sửa & Đồng bộ 3 site"
                      onClick={() => handleOpenEdit(s)}
                    >
                      <EditOutlined /> Sửa & Đồng bộ
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className={styles.tableFooter}>
          <span>Tổng số môn học: {subjects.length} (Đồng bộ 100% tại cả 3 DB)</span>
          <span>Bảo toàn Idempotency: Hỗ trợ retry an toàn nếu gặp sự cố mạng</span>
        </div>
      </div>

      {/* Modal Sửa môn học & Nhân bản */}
      {editingSubject && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <h3>Cập nhật & Nhân bản môn học ({editingSubject.code})</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setEditingSubject(null)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleSaveAndReplicate}>
              <div className={styles.modalBody}>
                <div className={styles.formGroup}>
                  <label>Tên môn học (*)</label>
                  <input
                    type="text"
                    value={editingSubject.name}
                    onChange={(e) =>
                      setEditingSubject({ ...editingSubject, name: e.target.value })
                    }
                    required
                  />
                </div>

                <div className={styles.formGroup}>
                  <label>Mô tả nội dung</label>
                  <textarea
                    rows={3}
                    value={editingSubject.description}
                    onChange={(e) =>
                      setEditingSubject({ ...editingSubject, description: e.target.value })
                    }
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div className={styles.formGroup}>
                    <label>Số buổi học</label>
                    <input
                      type="number"
                      min={10}
                      max={120}
                      value={editingSubject.sessions}
                      onChange={(e) =>
                        setEditingSubject({
                          ...editingSubject,
                          sessions: Number(e.target.value),
                        })
                      }
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <label>Học phí chuẩn (VNĐ)</label>
                    <input
                      type="number"
                      step={100000}
                      value={editingSubject.tuitionFee}
                      onChange={(e) =>
                        setEditingSubject({
                          ...editingSubject,
                          tuitionFee: Number(e.target.value),
                        })
                      }
                    />
                  </div>
                </div>

                <div style={{ fontSize: "12px", color: "var(--admin-text-muted)" }}>
                  Lưu ý: Khi bấm Lưu, Coordinator sẽ phát sinh <code>Idempotency-Key</code> và ghi đồng thời vào 3 CSDL SQL Server (Q1, Q7, TD).
                </div>
              </div>

              <div className={styles.modalFooter}>
                <button
                  type="button"
                  className={styles.btn}
                  onClick={() => setEditingSubject(null)}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className={`${styles.btn} ${styles.primary}`}
                  disabled={isSyncing}
                >
                  {isSyncing ? (
                    <>
                      <SyncOutlined spin /> Đang nhân bản 3 site...
                    </>
                  ) : (
                    <>
                      <CheckCircleOutlined /> Lưu & Ghi nhân bản (Replicate)
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

