import Link from "next/link";
import styles from "./CoursePreviewSection.module.scss";

export default function CoursePreviewSection() {
  return (
    <section className={styles.section} aria-labelledby="catalog-title">
      <div className={styles.inner}>
        <div className={styles.intro}>
          <p className={styles.eyebrow}>KHÁM PHÁ LỘ TRÌNH</p>
          <h2 id="catalog-title">Điều bạn muốn nói<br /><em>bắt đầu từ đâu?</em></h2>
          <p>Chọn mục tiêu học tập trước, rồi tìm hiểu khóa học và lịch phù hợp khi danh mục được cập nhật.</p>
          <Link href="/courses" className={styles.textLink}>Tới trang khóa học <span aria-hidden="true">→</span></Link>
        </div>
        <div className={styles.catalogCard}>
          <div className={styles.catalogHeader}><span className={styles.catalogIcon} aria-hidden="true">Aa</span><span>DANH MỤC CÔNG KHAI</span></div>
          <div className={styles.catalogBody}>
            <span className={styles.statusMark} aria-hidden="true">i</span>
            <h3>Thông tin khóa học đang được hoàn thiện</h3>
            <p>Trang công khai chưa nhận được danh mục từ API. Khi dữ liệu sẵn sàng, bạn có thể xem môn học, trình độ và lịch mở lớp tại đây.</p>
            <Link href="/courses">Xem trạng thái danh mục <span aria-hidden="true">↗</span></Link>
          </div>
          <div className={styles.catalogFoot}><span>KHÔNG HIỂN THỊ DỮ LIỆU GIẢ</span><span>01 — 03</span></div>
        </div>
      </div>
    </section>
  );
}
