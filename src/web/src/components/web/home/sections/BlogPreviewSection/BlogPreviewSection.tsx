/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { loadArticleCards } from "@/lib/content/publicArticles";
import styles from "./BlogPreviewSection.module.scss";

export default async function BlogPreviewSection() {
  const articles = await loadArticleCards();
  if (!articles.length) return null;
  return (
    <section className={styles.section} aria-labelledby="journal-title">
      <div className={styles.inner}>
        <div className={styles.top}><div><p className={styles.eyebrow}>GHI CHÚ HỌC TẬP</p><h2 id="journal-title">Học ngôn ngữ,<br /><span>bằng những điều nhỏ.</span></h2></div><p>Một vài gợi ý dễ áp dụng để bạn bắt đầu và giữ nhịp học mỗi ngày.</p></div>
        <div className={styles.grid}>{articles.slice(0, 3).map((article, index) => <article className={styles.card} key={article.slug}><div className={`${styles.art} ${styles[`art${index + 1}`]} ${article.cover ? styles.artCover : ""}`} aria-hidden="true">{article.cover ? <img className={styles.coverImg} src={article.cover} alt="" loading="lazy" /> : <><span>{String(index + 1).padStart(2, "0")}</span><i>{article.category}</i></>}</div><div className={styles.copy}><span className={styles.category}>{article.category} · {article.readingTime}</span><h3><Link href={`/blog/${article.slug}`}>{article.title}</Link></h3><p>{article.excerpt}</p><Link className={styles.read} href={`/blog/${article.slug}`}>Đọc bài viết <span aria-hidden="true">↗</span></Link></div></article>)}</div>
        <div className={styles.more}><span>NỘI DUNG THAM KHẢO · KHÔNG PHẢI TƯ VẤN CHUYÊN MÔN</span><Link href="/blog">Xem tất cả bài viết <span aria-hidden="true">→</span></Link></div>
      </div>
    </section>
  );
}
