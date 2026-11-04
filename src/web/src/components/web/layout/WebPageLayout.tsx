import type { ReactNode } from "react";
import styles from "./WebPageLayout.module.scss";
import WebFooter from "./WebFooter";
import WebHeader from "./WebHeader";

export default function WebPageLayout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.pageContainer}>
      <WebHeader />
      <main className={styles.mainContent}>{children}</main>
      <WebFooter />
    </div>
  );
}
