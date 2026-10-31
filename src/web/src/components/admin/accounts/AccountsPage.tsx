"use client";

import { useState } from "react";
import {
  IdcardOutlined,
  PlusOutlined,
  LockOutlined,
  UnlockOutlined,
  SafetyOutlined,
} from "@ant-design/icons";
import styles from "../common/AdminPageCommon.module.scss";

type AccountItem = {
  id: string;
  username: string;
  fullName: string;
  role: "admin_big" | "admin_small" | "ke_toan" | "le_tan";
  assignedSite: "ALL" | "Q1" | "Q7" | "TD";
  email: string;
  status: "active" | "locked";
  lastLogin: string;
};

const INITIAL_ACCOUNTS: AccountItem[] = [
  {
    id: "1",
    username: "quochieu_big",
    fullName: "Thái Trung Quốc Hiếu",
    role: "admin_big",
    assignedSite: "ALL",
    email: "quochieu@languagecenter.vn",
    status: "active",
    lastLogin: "30/10/2026 09:15",
  },
  {
    id: "2",
    username: "admin_q1",
    fullName: "Trần Văn Bình",
    role: "admin_small",
    assignedSite: "Q1",
    email: "admin.q1@languagecenter.vn",
    status: "active",
    lastLogin: "30/10/2026 08:30",
  },
  {
    id: "3",
    username: "admin_q7",
    fullName: "Lê Thị Thanh",
    role: "admin_small",
    assignedSite: "Q7",
    email: "admin.q7@languagecenter.vn",
    status: "active",
    lastLogin: "29/10/2026 17:45",
  },
  {
    id: "4",
    username: "admin_td",
    fullName: "Nguyễn Hoàng Nam",
    role: "admin_small",
    assignedSite: "TD",
    email: "admin.td@languagecenter.vn",
    status: "active",
    lastLogin: "30/10/2026 07:50",
  },
];

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountItem[]>(INITIAL_ACCOUNTS);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newAcc, setNewAcc] = useState({
    username: "",
    fullName: "",
    site: "Q1",
    email: "",
    role: "admin_small",
  });

  const handleToggleLock = (id: string) => {
    setAccounts(
      accounts.map((a) =>
        a.id === id
          ? { ...a, status: a.status === "active" ? "locked" : "active" }
          : a
      )
    );
  };

  const handleCreateAccount = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAcc.username.trim() || !newAcc.fullName.trim()) return;

    const created: AccountItem = {
      id: Date.now().toString(),
      username: newAcc.username.trim(),
      fullName: newAcc.fullName.trim(),
      role: newAcc.role as "admin_small" | "ke_toan" | "le_tan",
      assignedSite: newAcc.site as "Q1" | "Q7" | "TD",
      email: newAcc.email.trim() || `${newAcc.username}@languagecenter.vn`,
      status: "active",
      lastLogin: "Chưa đăng nhập",
    };

    setAccounts([...accounts, created]);
    setIsAddModalOpen(false);
    setNewAcc({ username: "", fullName: "", site: "Q1", email: "", role: "admin_small" });
  };

  const renderRoleBadge = (role: AccountItem["role"]) => {
    switch (role) {
      case "admin_big":
        return <span className={`${styles.badge} ${styles.global}`}>Admin Big (Toàn quyền)</span>;
      case "admin_small":
        return <span className={`${styles.badge} ${styles.site}`}>Admin Cơ sở</span>;
      case "ke_toan":
        return <span className={`${styles.badge} ${styles.active}`}>Kế toán</span>;
      case "le_tan":
        return <span className={`${styles.badge} ${styles.pending}`}>Lễ tân</span>;
    }
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1>Quản trị cơ sở & Nhân sự</h1>
            <span className={`${styles.badge} ${styles.global}`}>
              <SafetyOutlined /> Phân quyền phân tán
            </span>
          </div>
          <p className={styles.subtitle}>
            Tạo tài khoản Admin Small phụ trách cơ sở. Admin Small chỉ có quyền truy cập dữ liệu trong phạm vi site được phân công.
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            type="button"
            className={`${styles.btn} ${styles.primary}`}
            onClick={() => setIsAddModalOpen(true)}
          >
            <PlusOutlined /> Cấp tài khoản Admin Small
          </button>
        </div>
      </div>

      {/* Table */}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Tên đăng nhập</th>
                <th>Họ và tên</th>
                <th>Vai trò</th>
                <th>Cơ sở phụ trách</th>
                <th>Email nội bộ</th>
                <th>Lần đăng nhập cuối</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td>
                    <span className={styles.codeCell}>{a.username}</span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{a.fullName}</td>
                  <td>{renderRoleBadge(a.role)}</td>
                  <td>
                    <span className={`${styles.badge} ${styles.site}`}>
                      {a.assignedSite === "ALL" ? "Toàn bộ 3 cơ sở" : `Cơ sở ${a.assignedSite}`}
                    </span>
                  </td>
                  <td>{a.email}</td>
                  <td style={{ fontSize: "12px", color: "var(--admin-text-muted)" }}>
                    {a.lastLogin}
                  </td>
                  <td>
                    {a.status === "active" ? (
                      <span className={`${styles.badge} ${styles.active}`}>Hoạt động</span>
                    ) : (
                      <span className={`${styles.badge} ${styles.rejected}`}>Đã khóa</span>
                    )}
                  </td>
                  <td>
                    {a.role !== "admin_big" && (
                      <button
                        type="button"
                        className={`${styles.btn} ${styles.sm}`}
                        onClick={() => handleToggleLock(a.id)}
                        title={a.status === "active" ? "Khóa tài khoản" : "Mở khóa"}
                      >
                        {a.status === "active" ? <LockOutlined /> : <UnlockOutlined />}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className={styles.tableFooter}>
          <span>Bảo mật hệ thống: Mật khẩu được băm bằng bcrypt, phiên đăng nhập tự hết hạn sau 60 phút.</span>
        </div>
      </div>

      {/* Modal Thêm tài khoản */}
      {isAddModalOpen && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <h3>Cấp tài khoản Admin Small</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setIsAddModalOpen(false)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateAccount}>
              <div className={styles.modalBody}>
                <div className={styles.formGroup}>
                  <label>Cơ sở phân công (*)</label>
                  <select
                    value={newAcc.site}
                    onChange={(e) => setNewAcc({ ...newAcc, site: e.target.value })}
                  >
                    <option value="Q1">Cơ sở Quận 1 (QLTTNN_Q1)</option>
                    <option value="Q7">Cơ sở Quận 7 (QLTTNN_Q7)</option>
                    <option value="TD">Cơ sở Thủ Đức (QLTTNN_TD)</option>
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label>Tên đăng nhập (*)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: admin_q1_tan"
                    value={newAcc.username}
                    onChange={(e) => setNewAcc({ ...newAcc, username: e.target.value })}
                    required
                  />
                </div>

                <div className={styles.formGroup}>
                  <label>Họ và tên (*)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: Nguyễn Văn Tân"
                    value={newAcc.fullName}
                    onChange={(e) => setNewAcc({ ...newAcc, fullName: e.target.value })}
                    required
                  />
                </div>

                <div className={styles.formGroup}>
                  <label>Email cơ sở</label>
                  <input
                    type="email"
                    placeholder="tan.nguyen@languagecenter.vn"
                    value={newAcc.email}
                    onChange={(e) => setNewAcc({ ...newAcc, email: e.target.value })}
                  />
                </div>
              </div>

              <div className={styles.modalFooter}>
                <button
                  type="button"
                  className={styles.btn}
                  onClick={() => setIsAddModalOpen(false)}
                >
                  Hủy
                </button>
                <button type="submit" className={`${styles.btn} ${styles.primary}`}>
                  Cấp tài khoản
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

