import React from "react";
import styles from "./BranchesSection.module.scss";

interface CampusInfo {
  code: string;
  name: string;
  dbName: string;
  address: string;
  phone: string;
  classesCount: number;
  studentsCount: number;
  amenities: string[];
}

const CAMPUSES: CampusInfo[] = [
  {
    code: "Q1",
    name: "Cơ sở Quận 1 (Bến Nghé)",
    dbName: "QLTTNN_Q1",
    address: "Tòa nhà 45 Lê Duẩn, P. Bến Nghé, Quận 1, TP.HCM",
    phone: "(028) 3822 1199",
    classesCount: 22,
    studentsCount: 485,
    amenities: ["24 Phòng học Multimedia", "5 Phòng Lab Khảo thí", "Thư viện chuyên đề", "Hầm gửi xe ô tô"],
  },
  {
    code: "Q7",
    name: "Cơ sở Quận 7 (Tân Phú)",
    dbName: "QLTTNN_Q7",
    address: "128 Nguyễn Thị Thập, P. Tân Phú, Quận 7, TP.HCM",
    phone: "(028) 3775 2288",
    classesCount: 19,
    studentsCount: 420,
    amenities: ["18 Phòng học quốc tế", "Thư viện mở 300m²", "Khu cà phê tự học", "Bãi xe máy rộng rãi"],
  },
  {
    code: "TD",
    name: "Cơ sở Thủ Đức (Linh Chiểu)",
    dbName: "QLTTNN_TD",
    address: "250 Võ Văn Ngân, P. Linh Chiểu, TP. Thủ Đức, TP.HCM",
    phone: "(028) 3896 3377",
    classesCount: 21,
    studentsCount: 445,
    amenities: ["20 Phòng học máy lạnh", "Studio luyện phát âm", "Gần Làng Đại học", "Wifi chuyên dụng"],
  },
];

export default function BranchesSection() {
  return (
    <section className={styles.branchSection} id="branches">
      <div className={styles.branchInner}>
        {/* Section Header */}
        <div className={styles.sectionHeader}>
          <span className={styles.eyebrow}>Mạng lưới 3 cơ sở đào tạo</span>
          <h2 className={styles.title}>Hệ Thống Cơ Sở Trực Thuộc Tại TP.HCM</h2>
          <p className={styles.description}>
            Mỗi cơ sở được trang bị CSDL SQL Server độc lập và đồng bộ. Học viên có thể đăng ký
            học tập tại bất kỳ cơ sở nào gần nơi ở hoặc nơi làm việc, thuận tiện chuyển điểm học.
          </p>
        </div>

        {/* Campuses Grid */}
        <div className={styles.branchGrid}>
          {CAMPUSES.map((campus) => (
            <div className={styles.branchCard} key={campus.code}>
              <div className={styles.cardBanner}>
                <div className={styles.campusBadge}>
                  <span>MÃ SITE: {campus.code}</span>
                  <span>•</span>
                  <span>{campus.dbName}</span>
                </div>
                <div className={styles.statusPill}>
                  <span className={styles.dot} />
                  <span>CSDL Online</span>
                </div>
              </div>

              <div className={styles.cardMain}>
                <h3 className={styles.branchTitle}>{campus.name}</h3>

                <div className={styles.addressBox}>
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span>{campus.address}</span>
                </div>

                <div className={styles.phoneBox}>
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                  </svg>
                  <span>{campus.phone}</span>
                </div>

                <div className={styles.statsRow}>
                  <div className={styles.statItem}>
                    <span className={styles.statVal}>{campus.classesCount} Lớp</span>
                    <span className={styles.statLbl}>Đang khai giảng</span>
                  </div>
                  <div className={styles.statItem}>
                    <span className={styles.statVal}>{campus.studentsCount}</span>
                    <span className={styles.statLbl}>Học viên đang học</span>
                  </div>
                </div>

                <div className={styles.amenities}>
                  {campus.amenities.map((item, idx) => (
                    <span className={styles.amenityTag} key={idx}>
                      {item}
                    </span>
                  ))}
                </div>
              </div>

              <div className={styles.cardAction}>
                <a href="#consultation" className={styles.viewClassesBtn}>
                  <span>Xem lịch học tại {campus.code}</span>
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

