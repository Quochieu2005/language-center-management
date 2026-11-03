"use client";

import React, { useState } from "react";
import Link from "next/link";
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
    document.getElementById("courses")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section className={styles.hero}>
      <div className={styles.heroInner}>
        {/* Left Column: Heading, Pitch, Finder Box */}
        <div className={styles.heroContent}>
          <div className={styles.badgeWrapper}>
            <span className={styles.badgePulse} />
            <span className={styles.badgeText}>Khóa học ngoại ngữ tại TP. Hồ Chí Minh</span>
          </div>

          <h1 className={styles.heroTitle}>
            Chọn khóa học phù hợp với{" "}
            <span className={styles.highlight}>mục tiêu của bạn</span>
          </h1>

          <p className={styles.heroLead}>
            Xem các chương trình TOEIC, IELTS, giao tiếp và VSTEP. Chọn cơ sở cùng khung giờ bạn quan tâm,
            rồi gửi yêu cầu để được tư vấn trước khi đăng ký.
          </p>

          {/* Quick Course Finder Box */}
          <form className={styles.finderBox} onSubmit={handleSubmit}>
            <div className={styles.finderTitle}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span>Tìm chương trình và lớp học</span>
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
              <span>Xem khóa học</span>
            </button>
          </form>

          {/* Quick CTAs */}
          <div className={styles.heroActions}>
            <Link href="/#consultation" className={styles.ctaPrimary}>
              <span>Nhận tư vấn xếp lớp</span>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </Link>
          </div>
        </div>

        {/* Right Column: Course and campus overview */}
        <div className={styles.heroVisual}>
          {/* Campus choices */}
          <div className={styles.architectureCard}>
            <div className={styles.archHeader}>
              <span className={styles.archTitle}>Chọn cơ sở thuận tiện</span>
              <div className={styles.archStatus}>
                <span className={styles.dot} />
                <span>TP. Hồ Chí Minh</span>
              </div>
            </div>

            <div className={styles.sitePills}>
              <div className={styles.sitePill}>
                <span className={styles.siteCode}>Q1</span>
                <span className={styles.siteName}>Quận 1</span>
              </div>
              <div className={styles.sitePill}>
                <span className={styles.siteCode}>Q7</span>
                <span className={styles.siteName}>Quận 7</span>
              </div>
              <div className={styles.sitePill}>
                <span className={styles.siteCode}>TD</span>
                <span className={styles.siteName}>Thủ Đức</span>
              </div>
            </div>

            <p className={styles.archFootnote}>
              Chọn cơ sở dự kiến trong biểu mẫu tư vấn để trung tâm tiếp nhận đúng nhu cầu của bạn.
            </p>
          </div>

          {/* Course selection */}
          <div className={styles.visualCard}>
            <div className={styles.cardIcon}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <div className={styles.cardBody}>
              <div className={styles.cardLabel}>Chọn chương trình học</div>
              <div className={styles.cardDesc}>Xem các khóa TOEIC, IELTS, giao tiếp và VSTEP trước khi chọn lớp.</div>
            </div>
            <span className={styles.cardTag}>Theo mục tiêu học tập</span>
          </div>

          {/* Consultation */}
          <div className={styles.visualCard}>
            <div className={styles.cardIcon}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </div>
            <div className={styles.cardBody}>
              <div className={styles.cardLabel}>Cần tư vấn trước khi đăng ký?</div>
              <div className={styles.cardDesc}>Gửi thông tin khóa học và cơ sở bạn quan tâm ở biểu mẫu bên dưới.</div>
            </div>
            <span className={styles.cardTag}>Gửi yêu cầu tư vấn</span>
          </div>
        </div>
      </div>
    </section>
  );
}
