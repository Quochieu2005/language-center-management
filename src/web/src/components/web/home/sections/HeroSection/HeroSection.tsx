"use client";

import React, { useState } from "react";
import styles from "./HeroSection.module.scss";

interface HeroSectionProps {
  onSearch?: (branch: string, course: string, time: string) => void;
}

export default function HeroSection({ onSearch }: HeroSectionProps) {
  const [selectedBranch, setSelectedBranch] = useState("all");
  const [selectedCourse, setSelectedCourse] = useState("all");
  const [selectedTime, setSelectedTime] = useState("all");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSearch) {
      onSearch(selectedBranch, selectedCourse, selectedTime);
    }
    const coursesElem = document.getElementById("courses");
    if (coursesElem) {
      coursesElem.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <section className={styles.hero}>
      <div className={styles.heroInner}>
        {/* Left Column: Heading, Pitch, Finder Box */}
        <div className={styles.heroContent}>
          <div className={styles.badgeWrapper}>
            <span className={styles.badgePulse} />
            <span className={styles.badgeText}>Hệ thống Đào tạo & Quản lý Phân tán 3 Cơ sở</span>
          </div>

          <h1 className={styles.heroTitle}>
            Đào tạo Ngoại ngữ Chuẩn Quốc tế với{" "}
            <span className={styles.highlight}>Hạ tầng CSDL Phân tán</span>
          </h1>

          <p className={styles.heroLead}>
            Trải nghiệm học tập linh hoạt và nhất quán tại Quận 1, Quận 7 và Thủ Đức. Hệ thống phân tán
            giúp bảo toàn toàn diện lịch sử học viên, kết quả học tập và chuyển đổi cơ sở thuận tiện.
          </p>

          {/* Quick Course Finder Box */}
          <form className={styles.finderBox} onSubmit={handleSubmit}>
            <div className={styles.finderTitle}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span>Tìm kiếm & Đăng ký Lớp học tại 3 Cơ sở</span>
            </div>

            <div className={styles.finderGrid}>
              <div className={styles.filterGroup}>
                <label htmlFor="branch-select">Cơ sở đào tạo</label>
                <select
                  id="branch-select"
                  value={selectedBranch}
                  onChange={(e) => setSelectedBranch(e.target.value)}
                >
                  <option value="all">Tất cả 3 cơ sở</option>
                  <option value="Q1">Cơ sở Quận 1 (Bến Nghé)</option>
                  <option value="Q7">Cơ sở Quận 7 (Tân Phú)</option>
                  <option value="TD">Cơ sở Thủ Đức (Linh Chiểu)</option>
                </select>
              </div>

              <div className={styles.filterGroup}>
                <label htmlFor="course-select">Chương trình đào tạo</label>
                <select
                  id="course-select"
                  value={selectedCourse}
                  onChange={(e) => setSelectedCourse(e.target.value)}
                >
                  <option value="all">Tất cả chương trình</option>
                  <option value="TOEIC">TOEIC Đột phá 700+</option>
                  <option value="IELTS">IELTS Cam kết 6.5+</option>
                  <option value="COMM">Giao tiếp Phản xạ Quốc tế</option>
                  <option value="VSTEP">VSTEP B1 - B2</option>
                </select>
              </div>

              <div className={styles.filterGroup}>
                <label htmlFor="time-select">Khung giờ học</label>
                <select
                  id="time-select"
                  value={selectedTime}
                  onChange={(e) => setSelectedTime(e.target.value)}
                >
                  <option value="all">Mọi ca học</option>
                  <option value="T246">Tối Thứ 2 - 4 - 6 (18:00 - 20:30)</option>
                  <option value="T357">Tối Thứ 3 - 5 - 7 (18:00 - 20:30)</option>
                  <option value="WEEKEND">Cuối tuần (Sáng/Chiều T7 - CN)</option>
                </select>
              </div>
            </div>

            <button type="submit" className={styles.finderSubmit}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              <span>Xem danh sách lớp khả dụng</span>
            </button>
          </form>

          {/* Quick CTAs */}
          <div className={styles.heroActions}>
            <a href="#consultation" className={styles.ctaPrimary}>
              <span>Nhận tư vấn xếp lớp</span>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </a>
            <a href="#branches" className={styles.ctaSecondary}>
              Khám phá 3 Cơ sở
            </a>
          </div>
        </div>

        {/* Right Column: Visual Architecture Stack & Cards */}
        <div className={styles.heroVisual}>
          {/* Architecture Status Card */}
          <div className={styles.architectureCard}>
            <div className={styles.archHeader}>
              <span className={styles.archTitle}>Cấu trúc Hạ tầng CSDL 3 Site</span>
              <div className={styles.archStatus}>
                <span className={styles.dot} />
                <span>Hoạt động 100%</span>
              </div>
            </div>

            <div className={styles.sitePills}>
              <div className={styles.sitePill}>
                <span className={styles.siteCode}>Q1</span>
                <span className={styles.siteName}>Quận 1</span>
                <span className={styles.siteDb}>QLTTNN_Q1</span>
              </div>
              <div className={styles.sitePill}>
                <span className={styles.siteCode}>Q7</span>
                <span className={styles.siteName}>Quận 7</span>
                <span className={styles.siteDb}>QLTTNN_Q7</span>
              </div>
              <div className={styles.sitePill}>
                <span className={styles.siteCode}>TD</span>
                <span className={styles.siteName}>Thủ Đức</span>
                <span className={styles.siteDb}>QLTTNN_TD</span>
              </div>
            </div>

            <p className={styles.archFootnote}>
              Dữ liệu lớp học và học viên phân mảnh ngang độc lập theo từng cơ sở; bảng môn học được
              nhân bản đồng bộ thời gian thực.
            </p>
          </div>

          {/* Value prop 1: Concurrency Control */}
          <div className={styles.visualCard}>
            <div className={styles.cardIcon}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <div className={styles.cardBody}>
              <div className={styles.cardLabel}>Kiểm soát Đồng thời (Concurrency)</div>
              <div className={styles.cardDesc}>Khóa giao dịch giữ chỗ tự động, đảm bảo sĩ số không vượt quá sức chứa lớp học.</div>
            </div>
            <span className={styles.cardTag}>Chống trùng chỗ</span>
          </div>

          {/* Value prop 2: 2PC Transfers */}
          <div className={styles.visualCard}>
            <div className={styles.cardIcon}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </div>
            <div className={styles.cardBody}>
              <div className={styles.cardLabel}>Chuyển Cơ Sở Liền Mạch (2PC)</div>
              <div className={styles.cardDesc}>Điều phối giao dịch phân tán giữa nguồn và đích, bảo toàn lịch sử và điểm số.</div>
            </div>
            <span className={styles.cardTag}>Bảo toàn hồ sơ</span>
          </div>
        </div>
      </div>
    </section>
  );
}
