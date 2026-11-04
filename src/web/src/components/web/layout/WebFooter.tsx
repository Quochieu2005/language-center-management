import React from "react";
import Link from "next/link";
import styles from "./WebFooter.module.scss";

export default function WebFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        {/* Brand Column */}
        <div className={styles.brandCol}>
          <Link href="/" className={styles.footerLogo}>
            <div className={styles.logoIcon}>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="22" height="22">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div className={styles.brandTitle}>
              POLYGLOT
            </div>
          </Link>
          <p className={styles.brandDesc}>
            Các chương trình học ngoại ngữ tại Quận 1, Quận 7 và Thủ Đức. Xem khóa học hoặc gửi yêu cầu để được tư vấn.
          </p>
        </div>

        {/* Courses Links */}
        <div className={styles.footerCol}>
          <h4 className={styles.colTitle}>Chương trình đào tạo</h4>
          <ul className={styles.linkList}>
            <li><Link href="/courses">TOEIC 700+ Đột phá</Link></li>
            <li><Link href="/courses">IELTS Cam kết 6.5+</Link></li>
            <li><Link href="/courses">Tiếng Anh Giao tiếp Phản xạ</Link></li>
            <li><Link href="/courses">VSTEP B1 - B2 Cấp tốc</Link></li>
            <li><Link href="/courses">Luyện phát âm & Ngữ âm chuẩn</Link></li>
            <li><Link href="/courses">Tiếng Anh Thương mại (Business)</Link></li>
          </ul>
        </div>

        {/* Useful links */}
        <div className={styles.footerCol}>
          <h4 className={styles.colTitle}>Thông tin</h4>
          <ul className={styles.linkList}>
            <li><Link href="/courses">Chương trình khóa học</Link></li>
            <li><Link href="/blog">Blog</Link></li>
            <li><Link href="/#faq">Câu hỏi thường gặp</Link></li>
            <li><Link href="/contact">Tư vấn khóa học</Link></li>
          </ul>
        </div>

        {/* 3 Campuses Addresses */}
        <div className={styles.footerCol}>
          <h4 className={styles.colTitle}>Hệ thống 3 Cơ sở</h4>
          <div className={styles.branchesList}>
            <div className={styles.branchItem}>
              <div className={styles.branchName}>
                <span>Cơ sở Quận 1 (Q1)</span>
              </div>
              <p className={styles.branchAddr}>45 Lê Duẩn, P. Bến Nghé, Quận 1, TP.HCM</p>
            </div>

            <div className={styles.branchItem}>
              <div className={styles.branchName}>
                <span>Cơ sở Quận 7 (Q7)</span>
              </div>
              <p className={styles.branchAddr}>128 Nguyễn Thị Thập, P. Tân Phú, Quận 7, TP.HCM</p>
            </div>

            <div className={styles.branchItem}>
              <div className={styles.branchName}>
                <span>Cơ sở Thủ Đức (TD)</span>
              </div>
              <p className={styles.branchAddr}>250 Võ Văn Ngân, P. Linh Chiểu, TP. Thủ Đức, TP.HCM</p>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Legal & Metadata Bar */}
      <div className={styles.bottomBar}>
        <div className={styles.bottomInner}>
          <p className={styles.copyright}>
            © 2026 Polyglot Language Center.
          </p>
          <div className={styles.metaInfo}>
            <Link href="/admin" style={{ color: "#38bdf8" }}>Đăng nhập nhân viên</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

