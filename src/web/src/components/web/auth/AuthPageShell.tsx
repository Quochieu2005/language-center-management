import type { ReactNode } from "react";
import WebFooter from "@/components/web/layout/WebFooter";
import WebHeader from "@/components/web/layout/WebHeader";
import styles from "./AuthPageShell.module.scss";

export default function AuthPageShell({ children, eyebrow, title, description }: { children: ReactNode; eyebrow: string; title: string; description: string }) {
  return (
    <div className={styles.page}>
      <WebHeader />
      <main id="main-content" className={styles.main}>
        <div className={styles.inner}>
          <aside className={styles.story}>
            <p className={styles.eyebrow}>{eyebrow}</p>
            <h1>{title}</h1>
            <p className={styles.description}>{description}</p>
            <div className={styles.wordCard}>
              <span>WORD OF THE DAY</span>
              <strong>bonjour</strong>
              <i>/bɔ̃.ʒuʁ/</i>
              <small>xin chào · một cách mở đầu</small>
            </div>
            <p className={styles.caption}>Mỗi cuộc trò chuyện đều bắt đầu bằng một lời chào.</p>
          </aside>
          <section className={styles.formPanel} aria-label="Tài khoản">
            {children}
          </section>
        </div>
      </main>
      <WebFooter />
    </div>
  );
}
