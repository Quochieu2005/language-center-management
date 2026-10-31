"use client";

import { useState } from "react";
import {
  TeamOutlined,
  PlusOutlined,
  ReloadOutlined,
  KeyOutlined,
  EyeOutlined,
  DeleteOutlined,
  GlobalOutlined,
} from "@ant-design/icons";
import styles from "../common/AdminPageCommon.module.scss";

type StudentItem = {
  id: string;
  code: string;
  name: string;
  site: "Q1" | "Q7" | "TD";
  phone: string;
  email: string;
  status: "dang_hoc" | "bao_luu" | "da_chuyen_di" | "nghi_hoc";
  accountIssued: boolean;
  joinDate: string;
};

const INITIAL_STUDENTS: StudentItem[] = [
  {
    id: "1",
    code: "Q1-HV-000102",
    name: "Nguyễn Văn An",
    site: "Q1",
    phone: "0901234567",
    email: "an.nguyen@example.com",
    status: "dang_hoc",
    accountIssued: true,
    joinDate: "15/09/2026",
  },
  {
    id: "2",
    code: "Q7-HV-000089",
    name: "Trần Thị Mai",
    site: "Q7",
    phone: "0912345678",
    email: "mai.tran@example.com",
    status: "dang_hoc",
    accountIssued: false,
    joinDate: "20/09/2026",
  },
  {
    id: "3",
    code: "TD-HV-000215",
    name: "Lê Hoàng Long",
    site: "TD",
    phone: "0923456789",
    email: "long.le@example.com",
    status: "dang_hoc",
    accountIssued: true,
    joinDate: "01/10/2026",
  },
  {
    id: "4",
    code: "Q1-HV-000095",
    name: "Phạm Thùy Linh",
    site: "Q1",
    phone: "0934567890",
    email: "linh.pham@example.com",
    status: "da_chuyen_di",
    accountIssued: true,
    joinDate: "10/08/2026",
  },
  {
    id: "5",
    code: "TD-HV-000188",
    name: "Vũ Quốc Bảo",
    site: "TD",
    phone: "0945678901",
    email: "bao.vu@example.com",
    status: "bao_luu",
    accountIssued: false,
    joinDate: "12/07/2026",
  },
];

export default function StudentsPage() {
  const [students, setStudents] = useState<StudentItem[]>(INITIAL_STUDENTS);
  const [selectedSite, setSelectedSite] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [searchKeyword, setSearchKeyword] = useState<string>("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newStudent, setNewStudent] = useState({
    name: "",
    site: "Q1",
    phone: "",
    email: "",
  });

  const filteredStudents = students.filter((s) => {
    if (selectedSite !== "ALL" && s.site !== selectedSite) return false;
    if (selectedStatus !== "ALL" && s.status !== selectedStatus) return false;
    if (searchKeyword.trim() !== "") {
      const q = searchKeyword.toLowerCase();
      return (
        s.name.toLowerCase().includes(q) ||
        s.code.toLowerCase().includes(q) ||
        s.email.toLowerCase().includes(q) ||
        s.phone.includes(q)
      );
    }
    return true;
  });

  const handleCreateStudent = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStudent.name.trim()) return;

    const randomSuffix = Math.floor(1000 + Math.random() * 9000);
    const created: StudentItem = {
      id: Date.now().toString(),
      code: `${newStudent.site}-HV-00${randomSuffix}`,
      name: newStudent.name.trim(),
      site: newStudent.site as "Q1" | "Q7" | "TD",
      phone: newStudent.phone.trim() || "09xxxxxxxx",
      email: newStudent.email.trim() || "hocvien@example.com",
      status: "dang_hoc",
      accountIssued: false,
      joinDate: new Date().toLocaleDateString("vi-VN"),
    };

    setStudents([created, ...students]);
    setIsAddModalOpen(false);
    setNewStudent({ name: "", site: "Q1", phone: "", email: "" });
  };

  const handleIssueAccount = (code: string) => {
    setStudents(
      students.map((s) => (s.code === code ? { ...s, accountIssued: true } : s))
    );
  };

  const getStatusBadge = (status: StudentItem["status"]) => {
    switch (status) {
      case "dang_hoc":
        return <span className={`${styles.badge} ${styles.active}`}>Đang học</span>;
      case "bao_luu":
        return <span className={`${styles.badge} ${styles.pending}`}>Bảo lưu</span>;
      case "da_chuyen_di":
        return <span className={`${styles.badge} ${styles.rejected}`}>Đã chuyển đi</span>;
      case "nghi_hoc":
        return <span className={`${styles.badge} ${styles.rejected}`}>Nghỉ học</span>;
    }
  };

  return (
    <div className={styles.pageContainer}>
      {/* Header */}
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1>Hồ sơ học viên</h1>
            <span className={`${styles.badge} ${styles.global}`}>
              <GlobalOutlined /> Global Query (3 CSDL)
            </span>
          </div>
          <p className={styles.subtitle}>
            Quản lý hồ sơ học viên phân mảnh ngang tại các cơ sở Q1, Q7 và TD.
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            type="button"
            className={`${styles.btn} ${styles.primary}`}
            onClick={() => setIsAddModalOpen(true)}
          >
            <PlusOutlined /> Thêm học viên mới
          </button>
        </div>
      </div>

      {/* Toolbar & Filters */}
      <div className={styles.filterCard}>
        <div className={styles.filterGroup}>
          <input
            type="text"
            className={styles.searchInput}
            placeholder="Tìm theo mã học viên, họ tên, email, SĐT..."
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
          />

          <select
            className={styles.filterSelect}
            value={selectedSite}
            onChange={(e) => setSelectedSite(e.target.value)}
          >
            <option value="ALL">Tất cả cơ sở (Global)</option>
            <option value="Q1">Cơ sở Quận 1 (Q1)</option>
            <option value="Q7">Cơ sở Quận 7 (Q7)</option>
            <option value="TD">Cơ sở Thủ Đức (TD)</option>
          </select>

          <select
            className={styles.filterSelect}
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="dang_hoc">Đang học</option>
            <option value="bao_luu">Bảo lưu</option>
            <option value="da_chuyen_di">Đã chuyển đi (Lưu vết)</option>
            <option value="nghi_hoc">Nghỉ học</option>
          </select>
        </div>

        <button
          type="button"
          className={styles.btn}
          onClick={() => {
            setSelectedSite("ALL");
            setSelectedStatus("ALL");
            setSearchKeyword("");
          }}
          title="Đặt lại bộ lọc"
        >
          <ReloadOutlined /> Đặt lại
        </button>
      </div>

      {/* Data Table */}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Mã học viên</th>
                <th>Họ và tên</th>
                <th>Cơ sở lưu trữ</th>
                <th>Số điện thoại</th>
                <th>Email</th>
                <th>Trạng thái</th>
                <th>Tài khoản Portal</th>
                <th>Ngày nhập học</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {filteredStudents.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: "32px", color: "var(--admin-text-muted)" }}>
                    Không tìm thấy học viên nào phù hợp với bộ lọc.
                  </td>
                </tr>
              ) : (
                filteredStudents.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <span className={styles.codeCell}>{s.code}</span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{s.name}</td>
                    <td>
                      <span className={`${styles.badge} ${styles.site}`}>
                        {s.site === "Q1" ? "Quận 1" : s.site === "Q7" ? "Quận 7" : "Thủ Đức"}
                      </span>
                    </td>
                    <td>{s.phone}</td>
                    <td>{s.email}</td>
                    <td>{getStatusBadge(s.status)}</td>
                    <td>
                      {s.accountIssued ? (
                        <span style={{ color: "#10b981", fontSize: "12px", fontWeight: 600 }}>
                          ✓ Đã cấp
                        </span>
                      ) : (
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.sm}`}
                          onClick={() => handleIssueAccount(s.code)}
                          title="Cấp tài khoản đăng nhập portal"
                        >
                          <KeyOutlined /> Cấp TK
                        </button>
                      )}
                    </td>
                    <td style={{ color: "var(--admin-text-secondary)" }}>{s.joinDate}</td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.sm}`}
                          title="Xem hồ sơ chi tiết"
                        >
                          <EyeOutlined />
                        </button>
                        {s.status === "dang_hoc" && (
                          <button
                            type="button"
                            className={`${styles.btn} ${styles.sm} ${styles.danger}`}
                            title="Xóa mềm (Đánh dấu đã chuyển đi/nghỉ học)"
                            onClick={() => {
                              setStudents(
                                students.map((item) =>
                                  item.id === s.id ? { ...item, status: "da_chuyen_di" } : item
                                )
                              );
                            }}
                          >
                            <DeleteOutlined />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className={styles.tableFooter}>
          <span>
            Hiển thị <strong>{filteredStudents.length}</strong> / <strong>{students.length}</strong> học viên
            (Chỉ đếm bản ghi <code>dang_hoc</code> vào thống kê)
          </span>
          <span>Truy vấn Site Router: 3/3 site phản hồi tốt</span>
        </div>
      </div>

      {/* Modal Thêm học viên */}
      {isAddModalOpen && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <h3>Thêm mới hồ sơ học viên</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setIsAddModalOpen(false)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateStudent}>
              <div className={styles.modalBody}>
                <div className={styles.formGroup}>
                  <label>Cơ sở đăng ký tiếp nhận (*)</label>
                  <select
                    value={newStudent.site}
                    onChange={(e) => setNewStudent({ ...newStudent, site: e.target.value })}
                    required
                  >
                    <option value="Q1">Cơ sở Quận 1 (Tạo mã tiền tố Q1-HV-)</option>
                    <option value="Q7">Cơ sở Quận 7 (Tạo mã tiền tố Q7-HV-)</option>
                    <option value="TD">Cơ sở Thủ Đức (Tạo mã tiền tố TD-HV-)</option>
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label>Họ và tên học viên (*)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: Hoàng Minh Đức"
                    value={newStudent.name}
                    onChange={(e) => setNewStudent({ ...newStudent, name: e.target.value })}
                    required
                  />
                </div>

                <div className={styles.formGroup}>
                  <label>Số điện thoại</label>
                  <input
                    type="tel"
                    placeholder="09xxxxxxxx"
                    value={newStudent.phone}
                    onChange={(e) => setNewStudent({ ...newStudent, phone: e.target.value })}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label>Email liên hệ</label>
                  <input
                    type="email"
                    placeholder="hocvien@gmail.com"
                    value={newStudent.email}
                    onChange={(e) => setNewStudent({ ...newStudent, email: e.target.value })}
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
                  Lưu vào CSDL cơ sở
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

