"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type PublicCourse, type PublicCourseList } from "@/lib/api/catalog";
import PublicCourseEnrollmentDialog from "./PublicCourseEnrollmentDialog";
import styles from "./PublicCourseCatalog.module.scss";

const money = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });
const EMPTY_COURSES: PublicCourse[] = [];

function BranchList({ course }: { course: PublicCourse }) {
  if (!course.branches.length) return <span>Chưa có lớp mở được API xác nhận</span>;
  return <ul>{course.branches.map((branch) => <li key={branch.site_code}>{branch.site_name} · {branch.open_class_count} lớp đang mở</li>)}</ul>;
}

export default function PublicCourseCatalog({ courseSlug, preview = false }: { courseSlug?: string; preview?: boolean }) {
  const [catalog, setCatalog] = useState<PublicCourseList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [subject, setSubject] = useState("all");
  const [retry, setRetry] = useState(0);
  const [enrollmentCourse, setEnrollmentCourse] = useState<PublicCourse | null>(null);

  useEffect(() => {
    let active = true;
    catalogApi.publicCourses().then((result) => { if (active) { setCatalog(result); setError(""); } })
      .catch((reason: unknown) => { if (active) setError(reason instanceof ApiError ? reason.message : "Không kết nối được danh mục khóa học."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);

  const courses = catalog?.results ?? EMPTY_COURSES;
  const selectedCourse = courseSlug ? courses.find((course) => course.slug === courseSlug) : undefined;
  const subjects = useMemo(() => Array.from(new Map(courses.map((course) => [course.subject_id, course.subject_name])).entries()), [courses]);
  const subjectCourses = subject === "all" ? courses : courses.filter((course) => course.subject_id === subject);
  const visibleCourses = preview ? subjectCourses.slice(0, 3) : subjectCourses;

  if (courseSlug) {
    return <section className={styles.detail} aria-live="polite">
      {loading ? <p role="status">Đang tải thông tin khóa học…</p> : error ? <State message={error} retry={() => { setLoading(true); setRetry((value) => value + 1); }} /> : !selectedCourse ? <div><h2>Chưa tìm thấy khóa học</h2><p>Khóa học này không có trong danh mục công khai hiện tại.</p><Link href="/courses">Quay lại danh sách khóa học ↗</Link></div> : <article>
        <p className={styles.eyebrow}>{selectedCourse.subject_name} · {selectedCourse.level}</p>
        <h2>{selectedCourse.name}</h2>
        <p>Thông tin khóa học do danh mục công khai cung cấp.</p>
        <dl><div><dt>Thời lượng</dt><dd>{selectedCourse.session_count} buổi</dd></div><div><dt>Học phí chuẩn</dt><dd>{money.format(selectedCourse.standard_fee)}</dd></div></dl>
        <div className={styles.branchList}><strong>Cơ sở và lớp đang mở</strong><BranchList course={selectedCourse} /></div>
        {catalog && !catalog.complete && <Coverage catalog={catalog} />}
        <button className={styles.enroll} type="button" disabled={!selectedCourse.branches.length} onClick={() => setEnrollmentCourse(selectedCourse)}>Đăng ký lớp</button>
        <Link href="/courses">← Tất cả khóa học</Link>
      </article>}
      <PublicCourseEnrollmentDialog key={enrollmentCourse?.slug ?? "closed"} course={enrollmentCourse} onClose={() => setEnrollmentCourse(null)} />
    </section>;
  }

  return <section className={`${styles.catalog} ${preview ? styles.preview : ""}`} aria-labelledby={preview ? "home-course-title" : "public-catalog-title"} aria-live="polite">
    <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>{preview ? "DANH MỤC CÔNG KHAI" : "DANH MỤC TOÀN HỆ THỐNG"}</p><h2 id={preview ? "home-course-title" : "public-catalog-title"}>{preview ? "Khóa học để bạn khám phá" : "Khóa học hiện có"}</h2></div><p>Kết quả được tổng hợp từ các cơ sở đang hoạt động.</p></div>
    {catalog && !catalog.complete && <Coverage catalog={catalog} />}
    {loading ? <p className={styles.state} role="status">Đang tải danh sách khóa học…</p> : error ? <State message={error} retry={() => { setLoading(true); setRetry((value) => value + 1); }} /> : courses.length === 0 ? <p className={styles.state} role="status">Chưa có khóa học được công khai.</p> : <>
      <div className={styles.filters} aria-label="Lọc khóa học theo môn"><button type="button" aria-pressed={subject === "all"} onClick={() => setSubject("all")}>Tất cả</button>{subjects.map(([id, name]) => <button type="button" key={id} aria-pressed={subject === id} onClick={() => setSubject(id)}>{name}</button>)}</div>
      <div className={styles.grid}>{visibleCourses.map((course) => <article className={styles.course} key={course.course_id}><div className={styles.courseTop}><span>{course.subject_name} · {course.level}</span><strong>{money.format(course.standard_fee)}</strong></div><h3><Link href={`/courses/${course.slug}`}>{course.name}</Link></h3><p>{course.session_count} buổi học · {course.branches.reduce((total, branch) => total + branch.open_class_count, 0)} lớp đang mở</p><BranchList course={course} /><button className={styles.enroll} type="button" disabled={!course.branches.length} onClick={() => setEnrollmentCourse(course)}>Đăng ký lớp</button><Link className={styles.more} href={`/courses/${course.slug}`}>Xem chi tiết <span aria-hidden="true">↗</span></Link></article>)}</div>
      {preview && courses.length > 3 && <Link className={styles.allCourses} href="/courses">Xem toàn bộ khóa học <span aria-hidden="true">→</span></Link>}
    </>}
    <PublicCourseEnrollmentDialog key={enrollmentCourse?.slug ?? "closed"} course={enrollmentCourse} onClose={() => setEnrollmentCourse(null)} />
  </section>;
}

function Coverage({ catalog }: { catalog: PublicCourseList }) {
  return <p className={styles.coverage} role="status">Danh sách chưa đầy đủ. Site chưa kết nối: {[...catalog.missing_sites, ...catalog.inconsistent_sites].join(", ") || "một số cơ sở"}.</p>;
}

function State({ message, retry }: { message: string; retry: () => void }) {
  return <div className={styles.state} role="alert"><p>{message}</p><button type="button" onClick={retry}>Thử tải lại</button></div>;
}
