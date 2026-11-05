import Link from "next/link";
import styles from "./ContactSection.module.scss";

export default function ContactSection() {
  return (
    <section className={styles.section} aria-labelledby="contact-title">
      <div className={styles.inner}>
        <div><p className={styles.eyebrow}>BẠN ĐANG CẦN TÌM HIỂU?</p><h2 id="contact-title">Bắt đầu bằng<br /><span>một câu hỏi.</span></h2></div>
        <div className={styles.copy}><p>Thông tin liên hệ và biểu mẫu tư vấn chưa được kết nối với API. Bạn có thể xem trạng thái danh mục hoặc quay lại khi trung tâm công bố kênh liên hệ chính thức.</p><div className={styles.actions}><Link href="/contact">Trang liên hệ <span aria-hidden="true">↗</span></Link><Link href="/courses">Xem trạng thái khóa học <span aria-hidden="true">→</span></Link></div><span className={styles.note}>CHƯA CÓ EMAIL, SỐ ĐIỆN THOẠI HOẶC ĐỊA CHỈ ĐƯỢC XÁC NHẬN</span></div>
      </div>
    </section>
  );
}
