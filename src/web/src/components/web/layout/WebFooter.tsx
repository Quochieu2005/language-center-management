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
              POLYGLOT <span>DISTRIBUTED</span>
            </div>
          </Link>
          <p className={styles.brandDesc}>
            Hệ thống đào tạo ngoại ngữ tiêu chuẩn quốc tế ứng dụng kiến trúc Cơ sở Dữ liệu Phân tán hiện đại với 3 site độc lập tại Quận 1, Quận 7 và Thủ Đức.
          </p>
          <div className={styles.techBadge}>
            <span className={styles.dot} />
            <span>Mô hình 3 CSDL SQL Server Phân mảnh độc lập</span>
          </div>
        </div>

        {/* Courses Links */}
        <div className={styles.footerCol}>
          <h4 className={styles.colTitle}>Chương trình đào tạo</h4>
          <ul className={styles.linkList}>
            <li><a href="#courses">TOEIC 700+ Đột phá</a></li>
            <li><a href="#courses">IELTS Cam kết 6.5+</a></li>
            <li><a href="#courses">Tiếng Anh Giao tiếp Phản xạ</a></li>
            <li><a href="#courses">VSTEP B1 - B2 Cấp tốc</a></li>
            <li><a href="#courses">Luyện phát âm & Ngữ âm chuẩn</a></li>
            <li><a href="#courses">Tiếng Anh Thương mại (Business)</a></li>
          </ul>
        </div>

        {/* Tech & Architecture */}
        <div className={styles.footerCol}>
          <h4 className={styles.colTitle}>Công nghệ Phân tán</h4>
          <ul className={styles.linkList}>
            <li><a href="#technology">Phân mảnh ngang (LopHoc, HocVien)</a></li>
            <li><a href="#technology">Phân mảnh dẫn xuất (DangKy, Diem)</a></li>
            <li><a href="#technology">Replication thời gian thực (MonHoc)</a></li>
            <li><a href="#technology">Điều phối Chuyển cơ sở 2-Phase Commit</a></li>
            <li><a href="#technology">Kiểm soát đồng thời Concurrency</a></li>
            <li><a href="#technology">Global Distributed Query tổng hợp</a></li>
          </ul>
        </div>

        {/* 3 Campuses Addresses */}
        <div className={styles.footerCol}>
          <h4 className={styles.colTitle}>Hệ thống 3 Cơ sở</h4>
          <div className={styles.branchesList}>
            <div className={styles.branchItem}>
              <div className={styles.branchName}>
                <span>Cơ sở Quận 1 (Q1)</span>
                <span className={styles.branchTag}>QLTTNN_Q1</span>
              </div>
              <p className={styles.branchAddr}>45 Lê Duẩn, P. Bến Nghé, Quận 1, TP.HCM</p>
            </div>

            <div className={styles.branchItem}>
              <div className={styles.branchName}>
                <span>Cơ sở Quận 7 (Q7)</span>
                <span className={styles.branchTag}>QLTTNN_Q7</span>
              </div>
              <p className={styles.branchAddr}>128 Nguyễn Thị Thập, P. Tân Phú, Quận 7, TP.HCM</p>
            </div>

            <div className={styles.branchItem}>
              <div className={styles.branchName}>
                <span>Cơ sở Thủ Đức (TD)</span>
                <span className={styles.branchTag}>QLTTNN_TD</span>
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
            © 2026 Polyglot Distributed Language Center. Đồ án Cơ sở Dữ liệu Phân tán - Đề tài 10.
          </p>
          <div className={styles.metaInfo}>
            <span>Múi giờ: Asia/Ho_Chi_Minh</span>
            <span>•</span>
            <Link href="/admin" style={{ color: "#38bdf8" }}>Portal Cán bộ</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

