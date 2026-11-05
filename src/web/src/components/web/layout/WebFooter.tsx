import Link from "next/link";
import styles from "./WebFooter.module.scss";

export default function WebFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.brandBlock}>
          <Link className={styles.brand} href="/">
            <span className={styles.brandMark} aria-hidden="true">N</span>
            <span>[Tên trung tâm]</span>
          </Link>
          <p>Không gian để bắt đầu một ngôn ngữ mới, theo nhịp học phù hợp với bạn.</p>
        </div>
        <div className={styles.links}>
          <div><span className={styles.label}>Khám phá</span><Link href="/programs">Chương trình</Link><Link href="/courses">Khóa học</Link><Link href="/blog">Blog</Link></div>
          <div><span className={styles.label}>Thông tin</span><Link href="/branches">Cơ sở</Link><Link href="/contact">Liên hệ</Link><Link href="/login">Đăng nhập</Link></div>
        </div>
        <div className={styles.bottom}>
          <span>© {new Date().getFullYear()} · Quản lý trung tâm đào tạo ngoại ngữ</span>
          <span>Thông tin lớp và cơ sở được cập nhật từ hệ thống.</span>
        </div>
      </div>
    </footer>
  );
}
