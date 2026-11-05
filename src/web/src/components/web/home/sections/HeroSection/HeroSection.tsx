import Link from "next/link";
import styles from "./HeroSection.module.scss";

export default function HeroSection() {
  return (
    <section className={styles.hero} aria-labelledby="home-title">
      <div className={styles.inner}>
        <div className={styles.copy}>
          <p className={styles.eyebrow}><span /> BẮT ĐẦU TỪ ĐIỀU BẠN MUỐN NÓI</p>
          <h1 id="home-title">Một ngôn ngữ mới.<br /><em>Một cách nhìn mới.</em></h1>
          <p className={styles.intro}>Từng buổi học là một bước gần hơn tới cuộc trò chuyện bạn muốn có. Tìm hiểu lộ trình và chọn nơi học phù hợp với mình.</p>
          <div className={styles.actions}>
            <Link className={styles.primaryAction} href="/courses">Khám phá khóa học <span aria-hidden="true">↗</span></Link>
            <Link className={styles.secondaryAction} href="/branches">Tìm cơ sở <span aria-hidden="true">→</span></Link>
          </div>
          <div className={styles.note}><span className={styles.noteLine} /> Một khởi đầu nhỏ cũng tạo nên khác biệt.</div>
        </div>

        <div className={styles.art} aria-label="Một trang ghi chú học ngoại ngữ" role="img">
          <div className={styles.artTop}><span>GHI CHÚ NGÀY HÔM NAY</span><span>MỘT TỪ MỚI</span></div>
          <div className={styles.wordCard}>
            <span className={styles.wordLabel}>A SMALL STEP</span>
            <strong>hello</strong>
            <span className={styles.phonetic}>/həˈləʊ/ <i>interjection</i></span>
            <span className={styles.translation}>xin chào · bắt đầu một cuộc trò chuyện</span>
          </div>
          <div className={styles.handwriting}>say it<br />your way<span>↗</span></div>
          <div className={styles.artBottom}><span className={styles.dot} /><span>NGHE · NÓI · ĐỌC · VIẾT</span></div>
          <div className={styles.artIndex}>01</div>
        </div>
      </div>
      <div className={styles.scrollHint}><span /> CUỘN ĐỂ KHÁM PHÁ</div>
    </section>
  );
}
