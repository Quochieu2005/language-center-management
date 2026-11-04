"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type PublicCourse, type PublicCourseList } from "@/lib/api/catalog";
import styles from "./CoursePreviewSection.module.scss";

const formatMoney = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

function badgeStyle(subjectName: string) {
  const subject = subjectName.toLocaleLowerCase("vi");
  if (subject.includes("toeic")) return styles.toeic;
  if (subject.includes("ielts")) return styles.ielts;
  if (subject.includes("vstep")) return styles.vstep;
  if (subject.includes("giao tiếp") || subject.includes("communication")) return styles.comm;
  return styles.general;
}

function openClassCount(course: PublicCourse) {
  return course.branches.reduce((total, branch) => total + branch.open_class_count, 0);
}

export default function CoursePreviewSection() {
  const [catalog, setCatalog] = useState<PublicCourseList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeSubject, setActiveSubject] = useState("all");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let current = true;

    catalogApi.publicCourses()
      .then((result) => {
        if (current) {
          setCatalog(result);
          setActiveSubject("all");
        }
      })
      .catch((reason: unknown) => {
        if (current) {
          setCatalog(null);
          setError(reason instanceof ApiError ? reason.message : "Không kết nối được dịch vụ khóa học.");
        }
      })
      .finally(() => {
        if (current) setLoading(false);
      });

    return () => { current = false; };
  }, [reloadKey]);

  const courses = catalog?.results ?? [];
  const subjects = Array.from(
    new Map(courses.map((course) => [course.subject_id, course.subject_name])).entries(),
  );
  const filteredCourses = activeSubject === "all"
    ? courses
    : courses.filter((course) => course.subject_id === activeSubject);

  return (
    <section className={styles.courseSection} id="courses" aria-labelledby="courses-title">
      <div className={styles.courseInner}>
        <div className={styles.sectionHeader}>
          <span className={styles.eyebrow}>Chương trình đào tạo</span>
          <h2 className={styles.title} id="courses-title">Các khóa học ngoại ngữ</h2>
          <p className={styles.description}>
            Thông tin khóa học được tải từ danh mục của các cơ sở.
          </p>
        </div>

        {catalog && !catalog.complete && (
          <p className={styles.catalogNotice} role="status">
            Danh sách chưa đầy đủ. Chưa kết nối được: {[...catalog.missing_sites, ...catalog.inconsistent_sites].join(", ") || "một số cơ sở"}.
          </p>
        )}

        {!loading && !error && courses.length > 0 && (
          <div className={styles.filterTabs} aria-label="Lọc khóa học theo môn">
            <button
              type="button"
              className={`${styles.tabBtn} ${activeSubject === "all" ? styles.active : ""}`}
              aria-pressed={activeSubject === "all"}
              onClick={() => setActiveSubject("all")}
            >
              Tất cả khóa học
            </button>
            {subjects.map(([subjectId, subjectName]) => (
              <button
                key={subjectId}
                type="button"
                className={`${styles.tabBtn} ${activeSubject === subjectId ? styles.active : ""}`}
                aria-pressed={activeSubject === subjectId}
                onClick={() => setActiveSubject(subjectId)}
              >
                {subjectName}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <p className={styles.catalogState} role="status">Đang tải danh sách khóa học…</p>
        ) : error ? (
          <div className={styles.catalogState} role="alert">
            <p>{error}</p>
            <button
              type="button"
              className={styles.retryButton}
              onClick={() => {
                setLoading(true);
                setError("");
                setReloadKey((key) => key + 1);
              }}
            >
              Thử tải lại
            </button>
          </div>
        ) : filteredCourses.length === 0 ? (
          <p className={styles.catalogState} role="status">
            {courses.length === 0 ? "Chưa có khóa học được đăng tại các cơ sở." : "Không có khóa học thuộc môn này."}
          </p>
        ) : (
          <div className={styles.courseGrid}>
            {filteredCourses.map((course) => {
              const classCount = openClassCount(course);
              return (
                <article className={styles.courseCard} key={course.course_id}>
                  <div className={styles.cardTop}>
                    <div className={styles.tagRow}>
                      <span className={`${styles.courseBadge} ${badgeStyle(course.subject_name)}`}>
                        {course.subject_name} · {course.level}
                      </span>
                      <span className={styles.priceTag}>{formatMoney.format(course.standard_fee)}</span>
                    </div>
                    <h3 className={styles.courseTitle}>{course.name}</h3>
                    <p className={styles.courseSummary}>
                      Chương trình {course.subject_name} trình độ {course.level}, gồm {course.session_count} buổi học.
                    </p>
                  </div>

                  <div className={styles.cardBody}>
                    <ul className={styles.featuresList}>
                      {[
                        `Trình độ đào tạo: ${course.level}`,
                        `Thời lượng: ${course.session_count} buổi`,
                        `Học phí chuẩn: ${formatMoney.format(course.standard_fee)}`,
                        `${classCount} lớp đang mở`,
                      ].map((feature) => (
                        <li key={feature}>
                          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>

                    <div className={styles.branchesRow}>
                      <span className={styles.branchLabel}>Mở lớp tại:</span>
                      <div className={styles.branchPills}>
                        {course.branches.length > 0 ? course.branches.map((branch) => (
                          <span className={styles.branchPill} key={branch.site_code}>{branch.site_name}</span>
                        )) : <span className={styles.noBranches}>Chưa có lớp còn chỗ</span>}
                      </div>
                    </div>
                  </div>

                  <div className={styles.cardFooter}>
                    <Link href="/contact" className={styles.enrollBtn}>
                      <span>Đăng ký giữ chỗ</span>
                      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </Link>
                    <Link href="/contact" className={styles.detailBtn}>Hỏi lịch học</Link>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
