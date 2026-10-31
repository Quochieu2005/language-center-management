"use client";

import React, { useState } from "react";
import styles from "./CoursePreviewSection.module.scss";

interface CourseItem {
  id: string;
  category: "all" | "toeic" | "ielts" | "comm" | "vstep";
  badgeClass: string;
  badgeText: string;
  title: string;
  price: string;
  summary: string;
  features: string[];
  branches: string[];
}

const COURSES: CourseItem[] = [
  {
    id: "toeic-700",
    category: "toeic",
    badgeClass: styles.toeic,
    badgeText: "TOEIC 700+ Đột phá",
    title: "Luyện thi TOEIC 4 Kỹ Năng",
    price: "4.200.000 đ",
    summary: "Chương trình chuyên sâu rèn luyện phản xạ đề thi thực chiến, mẹo xử lý bẫy nghe và đọc nhanh.",
    features: [
      "Thời lượng: 24 buổi (3 tháng)",
      "Cam kết đầu ra tối thiểu 700+ điểm",
      "Giảng viên sở hữu 950+ TOEIC",
      "Thi thử miễn phí trên phần mềm mô phỏng",
    ],
    branches: ["Q1", "Q7", "TD"],
  },
  {
    id: "ielts-intensive",
    category: "ielts",
    badgeClass: styles.ielts,
    badgeText: "IELTS Intensive 6.5+",
    title: "IELTS Học Thuật Chuyên Sâu",
    price: "7.800.000 đ",
    summary: "Rèn luyện tư duy phản biện Writing Task 2 & Speaking Part 2-3 với đội ngũ chuyên gia giàu kinh nghiệm.",
    features: [
      "Thời lượng: 36 buổi (3.5 tháng)",
      "Sửa bài viết Writing 1-on-1 chi tiết",
      "Phòng Lab Speaking mô phỏng thi thật",
      "Cam kết đạt 6.5+ hoặc học lại miễn phí",
    ],
    branches: ["Q1", "Q7", "TD"],
  },
  {
    id: "comm-pro",
    category: "comm",
    badgeClass: styles.comm,
    badgeText: "Giao tiếp Quốc tế",
    title: "Tiếng Anh Phản Xạ Đi Làm",
    price: "3.900.000 đ",
    summary: "Tự tin thuyết trình, đàm phán hợp đồng, viết email thương mại và giao tiếp tự nhiên với đối tác nước ngoài.",
    features: [
      "Thời lượng: 24 buổi (2.5 tháng)",
      "50% thời lượng với Giáo viên bản ngữ",
      "Chủ đề thực tế: Họp, phỏng vấn, báo cáo",
      "Quy mô lớp nhỏ tối đa 16 học viên",
    ],
    branches: ["Q1", "Q7", "TD"],
  },
  {
    id: "vstep-b2",
    category: "vstep",
    badgeClass: styles.vstep,
    badgeText: "VSTEP B1 - B2",
    title: "Luyện thi Chuẩn Bộ GD&ĐT",
    price: "3.500.000 đ",
    summary: "Khóa học phục vụ xét tốt nghiệp đại học, thi công chức, thạc sĩ và nâng ngạch viên chức nhà nước.",
    features: [
      "Thời lượng: 20 buổi (2 tháng)",
      "Bộ ngân hàng đề sát thực tế kỳ thi",
      "Chiến thuật đạt điểm từng phần Nghe - Đọc",
      "Luyện viết luận bám sát thang điểm chuẩn",
    ],
    branches: ["Q1", "TD"],
  },
  {
    id: "ielts-foundation",
    category: "ielts",
    badgeClass: styles.ielts,
    badgeText: "IELTS Foundation",
    title: "Xây Gốc IELTS Từ Đầu",
    price: "5.500.000 đ",
    summary: "Khóa học dành cho người mất căn bản, củng cố ngữ pháp học thuật và 1.200 từ vựng Academic cốt lõi.",
    features: [
      "Thời lượng: 30 buổi (3 tháng)",
      "Hệ thống ngữ pháp trọng tâm thi cử",
      "Luyện phát âm chuẩn IPA từng âm vị",
      "Kiểm tra định kỳ 2 tuần/lần",
    ],
    branches: ["Q1", "Q7", "TD"],
  },
  {
    id: "toeic-speaking-writing",
    category: "toeic",
    badgeClass: styles.toeic,
    badgeText: "TOEIC Speaking & Writing",
    title: "TOEIC Nói & Viết Doanh Nghiệp",
    price: "4.800.000 đ",
    summary: "Hoàn thiện 4 kỹ năng toàn diện đáp ứng yêu cầu các tập đoàn đa quốc gia và doanh nghiệp nước ngoài.",
    features: [
      "Thời lượng: 24 buổi (2.5 tháng)",
      "Chấm bài nói và sửa âm giọng chuẩn",
      "Viết email công vụ đạt chuẩn CEFR B2",
      "Thực hành phỏng vấn xin việc tiếng Anh",
    ],
    branches: ["Q1", "Q7"],
  },
];

export default function CoursePreviewSection() {
  const [activeTab, setActiveTab] = useState<"all" | "toeic" | "ielts" | "comm" | "vstep">("all");

  const filteredCourses =
    activeTab === "all" ? COURSES : COURSES.filter((c) => c.category === activeTab);

  return (
    <section className={styles.courseSection} id="courses">
      <div className={styles.courseInner}>
        {/* Section Heading */}
        <div className={styles.sectionHeader}>
          <span className={styles.eyebrow}>Chương trình đào tạo chuẩn hóa</span>
          <h2 className={styles.title}>Các Khóa Học Ngoại Ngữ Trọng Điểm</h2>
          <p className={styles.description}>
            Giáo trình chuẩn quốc tế kết hợp phân mảnh dữ liệu lớp học theo 3 cơ sở (Q1, Q7, TD).
            Học viên dễ dàng theo dõi tiến độ học tập và bảo lưu kết quả xuyên suốt.
          </p>
        </div>

        {/* Filter Tabs */}
        <div className={styles.filterTabs}>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "all" ? styles.active : ""}`}
            onClick={() => setActiveTab("all")}
          >
            Tất cả khóa học
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "toeic" ? styles.active : ""}`}
            onClick={() => setActiveTab("toeic")}
          >
            TOEIC
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "ielts" ? styles.active : ""}`}
            onClick={() => setActiveTab("ielts")}
          >
            IELTS
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "comm" ? styles.active : ""}`}
            onClick={() => setActiveTab("comm")}
          >
            Giao tiếp Đi làm
          </button>
          <button
            type="button"
            className={`${styles.tabBtn} ${activeTab === "vstep" ? styles.active : ""}`}
            onClick={() => setActiveTab("vstep")}
          >
            VSTEP B1 - B2
          </button>
        </div>

        {/* Cards Grid */}
        <div className={styles.courseGrid}>
          {filteredCourses.map((course) => (
            <div className={styles.courseCard} key={course.id}>
              <div className={styles.cardTop}>
                <div className={styles.tagRow}>
                  <span className={`${styles.courseBadge} ${course.badgeClass}`}>
                    {course.badgeText}
                  </span>
                  <span className={styles.priceTag}>{course.price}</span>
                </div>
                <h3 className={styles.courseTitle}>{course.title}</h3>
                <p className={styles.courseSummary}>{course.summary}</p>
              </div>

              <div className={styles.cardBody}>
                <ul className={styles.featuresList}>
                  {course.features.map((feat, idx) => (
                    <li key={idx}>
                      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>

                <div className={styles.branchesRow}>
                  <span className={styles.branchLabel}>Mở lớp tại:</span>
                  <div className={styles.branchPills}>
                    {course.branches.map((b) => (
                      <span className={styles.branchPill} key={b}>
                        {b === "Q1" ? "Quận 1" : b === "Q7" ? "Quận 7" : "Thủ Đức"}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <a href="#consultation" className={styles.enrollBtn}>
                  <span>Đăng ký giữ chỗ</span>
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </a>
                <a href="#branches" className={styles.detailBtn}>
                  Lịch học
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
