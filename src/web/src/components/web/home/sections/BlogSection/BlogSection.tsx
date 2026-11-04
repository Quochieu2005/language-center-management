import Link from "next/link";
import styles from "./BlogSection.module.scss";

export default function BlogSection() {
  return (
    <section className={styles.blogSection} id="blog" aria-labelledby="blog-title">
      <div className={styles.blogInner}>
        <p className={styles.eyebrow}>Góc học ngoại ngữ</p>
        <h2 className={styles.title} id="blog-title">Blog</h2>
        <p className={styles.intro}>Bài viết và kinh nghiệm học ngoại ngữ sẽ được đăng tại đây.</p>
        <div className={styles.emptyState}>
          <h3>Chưa có bài viết</h3>
          <p>Nội dung sẽ xuất hiện khi có bài viết được đăng.</p>
          <Link href="/courses" className={styles.link}>Xem các khóa học</Link>
        </div>
      </div>
    </section>
  );
}
