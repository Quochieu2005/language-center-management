"use client";

import { useState } from "react";
import {
  CalendarOutlined,
  PlusOutlined,
  TeamOutlined,
  UserOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import styles from "../common/AdminPageCommon.module.scss";

type ClassItem = {
  id: string;
  classCode: string;
  name: string;
  subject: string;
  site: "Q1" | "Q7" | "TD";
  teacher: string;
  room: string;
  schedule: string;
  capacity: number;
  enrolled: number;
  status: "sap_mo" | "dang_hoc" | "da_ket_thuc";
  startDate: string;
};

const INITIAL_CLASSES: ClassItem[] = [
  {
    id: "1",
    classCode: "Q1-TOEIC-700-01",
    name: "TOEIC Đột Phá 700+",
    subject: "Tiếng Anh TOEIC",
    site: "Q1",
    teacher: "ThS. David Miller",
    room: "P.302 (Lab)",
    schedule: "Thứ 2 - 4 - 6 (18:00 - 20:00)",
    capacity: 25,
    enrolled: 24,
    status: "dang_hoc",
    startDate: "10/10/2026",
  },
  {
    id: "2",
    classCode: "Q7-IELTS-65-02",
    name: "IELTS Intensive 6.5",
    subject: "Tiếng Anh IELTS",
    site: "Q7",
    teacher: "Cô Sarah Johnson",
    room: "P.101",
    schedule: "Thứ 3 - 5 - 7 (18:30 - 20:30)",
    capacity: 20,
    enrolled: 18,
    status: "dang_hoc",
    startDate: "15/10/2026",
  },
  {
    id: "3",
    classCode: "TD-COMM-A2-01",
    name: "Giao Tiếp Phản Xạ Quốc Tế",
    subject: "Giao tiếp",
    site: "TD",
    teacher: "ThS. Trần Minh Tâm",
    room: "P.204",
    schedule: "Thứ 7 - CN (08:30 - 11:30)",
    capacity: 25,
    enrolled: 20,
    status: "sap_mo",
    startDate: "05/11/2026",
  },
  {
    id: "4",
    classCode: "Q1-VSTEP-B2-01",
    name: "Luyện Thi VSTEP B2 Chuẩn",
    subject: "Tiếng Anh VSTEP",
    site: "Q1",
    teacher: "ThS. Nguyễn Quỳnh Nga",
    room: "P.401",
    schedule: "Thứ 3 - 5 - 7 (19:30 - 21:00)",
    capacity: 30,
    enrolled: 28,
    status: "dang_hoc",
    startDate: "01/10/2026",
  },
];

export default function ClassesPage() {
  const [classes, setClasses] = useState<ClassItem[]>(INITIAL_CLASSES);
  const [selectedSite, setSelectedSite] = useState<string>("ALL");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isRosterModalOpen, setIsRosterModalOpen] = useState(false);
  const [activeClass, setActiveClass] = useState<ClassItem | null>(null);

  const [newClass, setNewClass] = useState({
    name: "",
    subject: "TOEIC",
    site: "Q1",
    teacher: "",
    room: "P.101",
    schedule: "Thứ 2 - 4 - 6 (18:00 - 20:00)",
    capacity: 25,
  });

  const filteredClasses = classes.filter((c) => {
    if (selectedSite !== "ALL" && c.site !== selectedSite) return false;
    return true;
  });

  const handleCreateClass = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClass.name.trim()) return;

    const created: ClassItem = {
      id: Date.now().toString(),
      classCode: `${newClass.site}-${newClass.subject.toUpperCase()}-${Math.floor(10 + Math.random() * 90)}`,
      name: newClass.name.trim(),
      subject: newClass.subject,
      site: newClass.site as "Q1" | "Q7" | "TD",
      teacher: newClass.teacher.trim() || "Chưa phân công",
      room: newClass.room,
      schedule: newClass.schedule,
      capacity: Number(newClass.capacity),
      enrolled: 0,
      status: "sap_mo",
      startDate: new Date().toLocaleDateString("vi-VN"),
    };

    setClasses([created, ...classes]);
    setIsAddModalOpen(false);
    setNewClass({
      name: "",
      subject: "TOEIC",
      site: "Q1",
      teacher: "",
      room: "P.101",
      schedule: "Thứ 2 - 4 - 6 (18:00 - 20:00)",
      capacity: 25,
    });
  };

  const handleViewRoster = (c: ClassItem) => {
    setActiveClass(c);
    setIsRosterModalOpen(true);
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1>Lớp học & Xếp lớp</h1>
            <span className={`${styles.badge} ${styles.site}`}>
              <CalendarOutlined /> Phân mảnh ngang theo cơ sở
            </span>
          </div>
          <p className={styles.subtitle}>
            Quản lý kế hoạch mở lớp, phòng học và kiểm soát sĩ số tranh chấp đồng thời (Concurrency Control).
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            type="button"
            className={`${styles.btn} ${styles.primary}`}
            onClick={() => setIsAddModalOpen(true)}
          >
            <PlusOutlined /> Mở lớp học mới
          </button>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className={styles.filterCard}>
        <div className={styles.filterGroup}>
          <select
            className={styles.filterSelect}
            value={selectedSite}
            onChange={(e) => setSelectedSite(e.target.value)}
          >
            <option value="ALL">Tất cả cơ sở (Phân mảnh ngang)</option>
            <option value="Q1">Lớp học Cơ sở Quận 1 (Q1)</option>
            <option value="Q7">Lớp học Cơ sở Quận 7 (Q7)</option>
            <option value="TD">Lớp học Cơ sở Thủ Đức (TD)</option>
          </select>
        </div>

        <span style={{ fontSize: "12.5px", color: "var(--admin-text-secondary)" }}>
          Đảm bảo kiểm tra sức chứa trong Transaction cục bộ để ngăn chặn Overbooking
        </span>
      </div>

      {/* Table */}
      <div className={styles.tableCard}>
        <div className={styles.tableWrapper}>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Mã lớp</th>
                <th>Tên lớp học</th>
                <th>Cơ sở</th>
                <th>Môn học</th>
                <th>Giảng viên</th>
                <th>Phòng học</th>
                <th>Lịch học</th>
                <th>Sĩ số / Sức chứa</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {filteredClasses.map((c) => {
                const isFull = c.enrolled >= c.capacity;
                return (
                  <tr key={c.id}>
                    <td>
                      <span className={styles.codeCell}>{c.classCode}</span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{c.name}</td>
                    <td>
                      <span className={`${styles.badge} ${styles.site}`}>{c.site}</span>
                    </td>
                    <td>{c.subject}</td>
                    <td>
                      <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <UserOutlined style={{ color: "#2c746b" }} /> {c.teacher}
                      </span>
                    </td>
                    <td>{c.room}</td>
                    <td style={{ fontSize: "12px", color: "var(--admin-text-secondary)" }}>
                      {c.schedule}
                    </td>
                    <td>
                      <span
                        style={{
                          fontWeight: 700,
                          color: isFull ? "#ef4444" : "#10b981",
                        }}
                      >
                        {c.enrolled}/{c.capacity}
                      </span>
                      {isFull && (
                        <span style={{ fontSize: "10px", marginLeft: "4px", color: "#ef4444" }}>
                          (Hết chỗ)
                        </span>
                      )}
                    </td>
                    <td>
                      {c.status === "dang_hoc" ? (
                        <span className={`${styles.badge} ${styles.active}`}>Đang học</span>
                      ) : (
                        <span className={`${styles.badge} ${styles.pending}`}>Sắp mở</span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className={`${styles.btn} ${styles.sm}`}
                        title="Xem danh sách học viên (Roster)"
                        onClick={() => handleViewRoster(c)}
                      >
                        <TeamOutlined /> Roster
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className={styles.tableFooter}>
          <span>Hiển thị {filteredClasses.length} lớp học đang hoạt động</span>
          <span>Bảo vệ Concurrency: Khóa mức cô lập Serializable / Row-level Lock</span>
        </div>
      </div>

      {/* Modal Mở lớp mới */}
      {isAddModalOpen && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div className={styles.modalHeader}>
              <h3>Mở lớp học mới tại cơ sở</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setIsAddModalOpen(false)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateClass}>
              <div className={styles.modalBody}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div className={styles.formGroup}>
                    <label>Cơ sở tổ chức (*)</label>
                    <select
                      value={newClass.site}
                      onChange={(e) => setNewClass({ ...newClass, site: e.target.value })}
                    >
                      <option value="Q1">Quận 1 (Q1)</option>
                      <option value="Q7">Quận 7 (Q7)</option>
                      <option value="TD">Thủ Đức (TD)</option>
                    </select>
                  </div>

                  <div className={styles.formGroup}>
                    <label>Môn học (*)</label>
                    <select
                      value={newClass.subject}
                      onChange={(e) => setNewClass({ ...newClass, subject: e.target.value })}
                    >
                      <option value="TOEIC">Tiếng Anh TOEIC</option>
                      <option value="IELTS">Tiếng Anh IELTS</option>
                      <option value="Giao tiếp">Tiếng Anh Giao tiếp</option>
                      <option value="VSTEP">Tiếng Anh VSTEP</option>
                    </select>
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label>Tên lớp học (*)</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: TOEIC 650+ Khóa 28"
                    value={newClass.name}
                    onChange={(e) => setNewClass({ ...newClass, name: e.target.value })}
                    required
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div className={styles.formGroup}>
                    <label>Giảng viên phụ trách</label>
                    <input
                      type="text"
                      placeholder="ThS. David Miller"
                      value={newClass.teacher}
                      onChange={(e) => setNewClass({ ...newClass, teacher: e.target.value })}
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <label>Phòng học</label>
                    <input
                      type="text"
                      placeholder="P.201"
                      value={newClass.room}
                      onChange={(e) => setNewClass({ ...newClass, room: e.target.value })}
                    />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "12px" }}>
                  <div className={styles.formGroup}>
                    <label>Lịch học</label>
                    <input
                      type="text"
                      placeholder="Thứ 2 - 4 - 6 (18:00 - 20:00)"
                      value={newClass.schedule}
                      onChange={(e) => setNewClass({ ...newClass, schedule: e.target.value })}
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <label>Sức chứa (*)</label>
                    <input
                      type="number"
                      min={5}
                      max={60}
                      value={newClass.capacity}
                      onChange={(e) => setNewClass({ ...newClass, capacity: Number(e.target.value) })}
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
                  Tạo lớp vào CSDL cơ sở
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Xem Danh sách học viên trong lớp */}
      {isRosterModalOpen && activeClass && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard} style={{ maxWidth: "600px" }}>
            <div className={styles.modalHeader}>
              <h3>Danh sách học viên: {activeClass.name}</h3>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setIsRosterModalOpen(false)}
              >
                ×
              </button>
            </div>

            <div className={styles.modalBody}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12.5px" }}>
                <span>Mã lớp: <strong>{activeClass.classCode}</strong></span>
                <span>Cơ sở: <strong>{activeClass.site}</strong></span>
                <span>Sĩ số hiện tại: <strong>{activeClass.enrolled}/{activeClass.capacity}</strong></span>
              </div>

              <table className={styles.dataTable} style={{ marginTop: "10px" }}>
                <thead>
                  <tr>
                    <th>STT</th>
                    <th>Mã học viên</th>
                    <th>Họ và tên</th>
                    <th>Ngày đăng ký</th>
                    <th>Học phí</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>1</td>
                    <td><span className={styles.codeCell}>{activeClass.site}-HV-000102</span></td>
                    <td style={{ fontWeight: 600 }}>Nguyễn Văn An</td>
                    <td>12/10/2026</td>
                    <td><span className={`${styles.badge} ${styles.active}`}>Đã đóng</span></td>
                  </tr>
                  <tr>
                    <td>2</td>
                    <td><span className={styles.codeCell}>{activeClass.site}-HV-000145</span></td>
                    <td style={{ fontWeight: 600 }}>Trần Bảo Long</td>
                    <td>14/10/2026</td>
                    <td><span className={`${styles.badge} ${styles.active}`}>Đã đóng</span></td>
                  </tr>
                  <tr>
                    <td>3</td>
                    <td><span className={styles.codeCell}>{activeClass.site}-HV-000219</span></td>
                    <td style={{ fontWeight: 600 }}>Lê Thị Hoàng Yến</td>
                    <td>16/10/2026</td>
                    <td><span className={`${styles.badge} ${styles.pending}`}>Còn nợ</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className={styles.modalFooter}>
              <button
                type="button"
                className={styles.btn}
                onClick={() => setIsRosterModalOpen(false)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

