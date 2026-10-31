"use client";

import { useState } from "react";
import {
  UsergroupAddOutlined,
  PlusOutlined,
  CheckCircleOutlined,
  StopOutlined,
} from "@ant-design/icons";
import styles from "../common/AdminPageCommon.module.scss";

type TeacherItem = {
  id: string;
  code: string;
  name: string;
  site: "Q1" | "Q7" | "TD";
  email: string;
  phone: string;
  specialty: string;
  activeClasses: number;
  status: "active" | "inactive";
};

const INITIAL_TEACHERS: TeacherItem[] = [
  {
    id: "1",
    code: "GV-001",
    name: "ThS. David Miller",
    site: "Q1",
    email: "david.miller@example.com",
    phone: "0981234567",
    specialty: "TOEIC & Business English",
    activeClasses: 3,
    status: "active",
  },
  {
    id: "2",
    code: "GV-002",
    name: "Cô Sarah Johnson",
    site: "Q7",
    email: "sarah.j@example.com",
    phone: "0982345678",
    specialty: "IELTS Speaking & Writing",
    activeClasses: 2,
    status: "active",
  },
  {
    id: "3",
    code: "GV-003",
    name: "ThS. Trần Minh Tâm",
    site: "TD",
    email: "tam.tran@example.com",
    phone: "0983456789",
    specialty: "Giao tiếp phản xạ",
    activeClasses: 2,
    status: "active",
  },
  {
    id: "4",
    code: "GV-004",
    name: "ThS. Nguyễn Quỳnh Nga",
    site: "Q1",
    email: "nga.nguyen@example.com",
    phone: "0984567890",
    specialty: "VSTEP & Ngữ pháp nâng cao",
    activeClasses: 1,
    status: "active",
  },
];

export default function TeachersPage() {
  const [teachers, setTeachers] = useState<TeacherItem[]>(INITIAL_TEACHERS);
  const [selectedSite, setSelectedSite] = useState<string>("ALL");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newTeacher, setNewTeacher] = useState({
    name: "",
    site: "Q1",
    email: "",
    phone: "",
    specialty: "",
  });

  const filteredTeachers = teachers.filter((t) => {
    if (selectedSite !== "ALL" && t.site !== selectedSite) return false;
    return true;
  });

  const handleToggleStatus = (id: string) => {
    setTeachers(
      teachers.map((t) =>
        t.id === id
          ? { ...t, status: t.status === "active" ? "inactive" : "active" }
          : t
      )
    );
  };

  const handleCreateTeacher = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeacher.name.trim()) return;

    const created: TeacherItem = {
      id: Date.now().toString(),
      code: `GV-00${teachers.length + 1}`,
      name: newTeacher.name.trim(),
      site: newTeacher.site as "Q1" | "Q7" | "TD",
      email: newTeacher.email.trim() || "gv@example.com",
      phone: newTeacher.phone.trim() || "098xxxxxxx",
      specialty: newTeacher.specialty.trim() || "Tiếng Anh Tổng Quát",
      activeClasses: 0,
      status: "active",
    };

    setTeachers([...teachers, created]);
    setIsAddModalOpen(false);
    setNewTeacher({ name: "", site: "Q1", email: "", phone: "", specialty: "" });
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1>Giảng viên & Roster</h1>
            <span className={`${styles.badge} ${styles.site}`}>
              <UsergroupAddOutlined /> Quản lý nhân sự theo cơ sở
            </span>
          </div>
          <p className={styles.subtitle}>
            Hồ sơ đội ngũ giảng viên, phân công lớp và lịch giảng dạy tại các cơ sở.
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            type="button"
            className={`${styles.btn} ${styles.primary}`}
            onClick={() => setIsAddModalOpen(true)}
          >
            <PlusOutlined /> Thêm giảng viên mới
          </button>
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
            <option value="Q1">Cơ sở Quận 1 (Q1)</option>
            <option value="Q7">Cơ sở Quận 7 (Q7)</option>
            <option value="TD">Cơ sở Thủ Đức (TD)</option>
          </select>
        </div>

        <span style={{ fontSize: "12.5px", color: "var(--admin-text-secondary)" }}>
          Chỉ Admin Big và Admin Small đúng cơ sở được quyền quản lý giảng viên
        </span>
      </div>

      {/* Table */}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Mã GV</th>
                <th>Họ và tên</th>
                <th>Cơ sở chính</th>
                <th>Chuyên môn giảng dạy</th>
                <th>Email</th>
                <th>Số điện thoại</th>
                <th>Số lớp phụ trách</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {filteredTeachers.map((t) => (
                <tr key={t.id}>
                  <td>
                    <span className={styles.codeCell}>{t.code}</span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{t.name}</td>
                  <td>
                    <span className={`${styles.badge} ${styles.site}`}>{t.site}</span>
                  </td>
                  <td>{t.specialty}</td>
                  <td>{t.email}</td>
                  <td>{t.phone}</td>
                  <td style={{ fontWeight: 600, color: "#2c746b" }}>{t.activeClasses} lớp</td>
                  <td>
                    {t.status === "active" ? (
                      <span className={`${styles.badge} ${styles.active}`}>Đang giảng dạy</span>
                    ) : (
                      <span className={`${styles.badge} ${styles.rejected}`}>Tạm dừng</span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`${styles.btn} ${styles.sm}`}
                      onClick={() => handleToggleStatus(t.id)}
                      title={t.status === "active" ? "Tạm ngưng giảng dạy" : "Kích hoạt lại"}
                    >
                      {t.status === "active" ? <StopOutlined /> : <CheckCircleOutlined />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className={styles.tableFooter}>
          <span>Tổng số giảng viên: {filteredTeachers.length}</span>
          <span>Phân công lớp học trực tiếp qua giao diện Roster</span>
        </div>
      </div>

      {/* Modal Thêm Giảng viên */}
      {isAddModalOpen && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <h3>Thêm mới giảng viên</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setIsAddModalOpen(false)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateTeacher}>
              <div className={styles.modalBody}>
                <div className={styles.formGroup}>
                  <label>Cơ sở chính (*)</label>
                  <select
                    value={newTeacher.site}
                    onChange={(e) => setNewTeacher({ ...newTeacher, site: e.target.value })}
                  >
                    <option value="Q1">Quận 1 (Q1)</option>
                    <option value="Q7">Quận 7 (Q7)</option>
                    <option value="TD">Thủ Đức (TD)</option>
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label>Họ và tên giảng viên (*)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: ThS. David Miller"
                    value={newTeacher.name}
                    onChange={(e) => setNewTeacher({ ...newTeacher, name: e.target.value })}
                    required
                  />
                </div>

                <div className={styles.formGroup}>
                  <label>Chuyên môn chính</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: IELTS Speaking & Writing 8.0"
                    value={newTeacher.specialty}
                    onChange={(e) => setNewTeacher({ ...newTeacher, specialty: e.target.value })}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div className={styles.formGroup}>
                    <label>Email</label>
                    <input
                      type="email"
                      placeholder="gv@example.com"
                      value={newTeacher.email}
                      onChange={(e) => setNewTeacher({ ...newTeacher, email: e.target.value })}
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <label>Số điện thoại</label>
                    <input
                      type="tel"
                      placeholder="098xxxxxxx"
                      value={newTeacher.phone}
                      onChange={(e) => setNewTeacher({ ...newTeacher, phone: e.target.value })}
                    />
                  </div>
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
                  Lưu hồ sơ giảng viên
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

