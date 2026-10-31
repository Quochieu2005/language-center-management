import React from "react";
import styles from "./BenefitsSection.module.scss";

interface TechBenefit {
  icon: React.ReactNode;
  title: string;
  description: string;
  tag: string;
}

const BENEFITS: TechBenefit[] = [
  {
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
      </svg>
    ),
    title: "Phân Mảnh Ngang CSDL (Horizontal Partitioning)",
    description: "Dữ liệu lớp học và học viên được phân mảnh độc lập về từng cơ sở (Q1, Q7, TD). Hệ thống phản hồi tức thì dưới 50ms, triệt tiêu nguy cơ nghẽn mạng vào ngày cao điểm mở lớp.",
    tag: "Tối ưu hiệu năng 3 site",
  },
  {
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
      </svg>
    ),
    title: "Chuyển Cơ Sở Liền Mạch (2-Phase Commit)",
    description: "Học viên được phép chuyển chi nhánh học khi thay đổi nơi cư trú. Bộ điều phối Coordinator kiểm tra 2 pha đảm bảo ghi nhận đồng thời tại nguồn & đích, bảo toàn nguyên vẹn điểm số.",
    tag: "Bảo toàn hồ sơ 100%",
  },
  {
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
    ),
    title: "Nhân Bản Đồng Bộ (Master Replication)",
    description: "Bảng dữ liệu danh mục môn học, khóa học và chính sách chuẩn được nhân bản đồng bộ thời gian thực sang cả 3 CSDL, đảm bảo chương trình đào tạo luôn chuẩn hóa và nhất quán.",
    tag: "Đồng bộ tức thì",
  },
  {
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
      </svg>
    ),
    title: "Kiểm Soát Xung Đột Đồng Thời (Concurrency)",
    description: "Thuật toán kiểm soát khóa phiên độc lập ngăn chặn tình trạng nhiều học viên cùng đăng ký chỗ học cuối cùng, cam kết sĩ số lớp luôn chính xác tuyệt đối theo sức chứa phòng.",
    tag: "Chống trùng chỗ học",
  },
  {
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
    title: "Phân Quyền Chặt Chẽ (Multi-Role RBAC)",
    description: "Tách bạch phạm vi quản trị: Admin Big quản lý tổng thể 3 cơ sở, Admin Small quản lý riêng chi nhánh phụ trách, Giáo viên xem lớp và nhập điểm thi theo đúng phân công.",
    tag: "An toàn dữ liệu",
  },
  {
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    title: "Báo Cáo Phân Tán (Global Distributed Query)",
    description: "Site Router truy vấn song song cả 3 cơ sở để tổng hợp báo cáo học viên đang theo học, số lớp hoạt động và doanh thu mà không cần gộp chung CSDL hay dùng JOIN xuyên site.",
    tag: "Báo cáo toàn cục",
  },
];

export default function BenefitsSection() {
  return (
    <section className={styles.benefitSection} id="technology">
      <div className={styles.benefitInner}>
        {/* Section Header */}
        <div className={styles.sectionHeader}>
          <span className={styles.eyebrow}>Kiến trúc kỹ thuật cốt lõi</span>
          <h2 className={styles.title}>Lợi Thế Vượt Trội Từ Hạ Tầng CSDL Phân Tán</h2>
          <p className={styles.description}>
            Khác biệt hoàn toàn so với mô hình cơ sở dữ liệu đơn lẻ truyền thống, kiến trúc 3 site
            độc lập đem lại trải nghiệm học tập ổn định, bảo mật và linh hoạt tối đa.
          </p>
        </div>

        {/* Benefits Cards Grid */}
        <div className={styles.cardsGrid}>
          {BENEFITS.map((item, idx) => (
            <div className={styles.techCard} key={idx}>
              <div className={styles.iconBox}>{item.icon}</div>
              <h3 className={styles.cardTitle}>{item.title}</h3>
              <p className={styles.cardDesc}>{item.description}</p>
              <span className={styles.cardTag}>{item.tag}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

