import Link from "next/link";
import styles from "./FinalCTASection.module.scss";

export default function FinalCTASection() {
  return (
    <section className={styles.section} aria-labelledby="next-step-title">
      <div className={styles.inner}>
        <div><p className={styles.eyebrow}>BƯỚC TIẾP THEO</p><h2 id="next-step-title">Sẵn sàng bắt đầu<br /><em>một cuộc trò chuyện?</em></h2></div>
        <div className={styles.actionBlock}>
          <p>Khám phá thông tin khóa học và cơ sở đang được cập nhật trên website.</p>
          <div className={styles.actions}><Link href="/courses">Xem khóa học <span aria-hidden="true">↗</span></Link><Link href="/branches">Tìm cơ sở <span aria-hidden="true">→</span></Link></div>
        </div>
        <span className={styles.watermark} aria-hidden="true">Aa</span>
      </div>
    </section>
  );
}
