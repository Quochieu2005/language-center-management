import Link from "next/link";
import WebFooter from "@/components/web/layout/WebFooter";
import WebHeader from "@/components/web/layout/WebHeader";
import PublicCourseCatalog from "./PublicCourseCatalog";
import styles from "./PublicCatalogPage.module.scss";

type CatalogKind = "courses" | "branches" | "course-detail";

const content: Record<CatalogKind, { eyebrow: string; title: string; description: string; label: string; note: string }> = {
  courses: {
    eyebrow: "DANH MỤC KHÓA HỌC",
    title: "Tìm lộ trình\nphù hợp với bạn.",
    description: "Khám phá môn học, trình độ, học phí và cơ sở từ danh mục công khai toàn hệ thống.",
    label: "Dữ liệu tổng hợp từ các cơ sở",
    note: "Danh mục được tải qua API. Nếu một cơ sở chưa kết nối, trạng thái thiếu site sẽ được hiển thị cùng kết quả.",
  },
  branches: {
    eyebrow: "CÁC CƠ SỞ",
    title: "Chọn nơi học\ngần với bạn.",
    description: "Thông tin cơ sở, địa chỉ và liên hệ sẽ được hiển thị từ dữ liệu đang hoạt động của trung tâm.",
    label: "Thông tin cơ sở chưa khả dụng",
    note: "Trang công khai chưa có API để tải danh sách cơ sở. Không có địa chỉ hoặc thông tin liên hệ nào được tự điền.",
  },
  "course-detail": {
    eyebrow: "CHI TIẾT KHÓA HỌC",
    title: "Thông tin lớp\nđang được cập nhật.",
    description: "Chi tiết môn học, trình độ, học phí và lịch học sẽ được lấy từ danh mục chính thức.",
    label: "Chưa tìm thấy thông tin khóa học",
    note: "Đường dẫn này chưa có khóa học công khai tương ứng. Hãy quay lại danh mục để xem trạng thái cập nhật.",
  },
};

export default function PublicCatalogPage({ kind, slug }: { kind: CatalogKind; slug?: string }) {
  const page = content[kind];
  return (
    <div className={styles.page}>
      <WebHeader />
      <main id="main-content" className={styles.main}>
        <div className={styles.breadcrumb}><Link href="/">Trang chủ</Link><span aria-hidden="true">/</span><span>{kind === "branches" ? "Cơ sở" : "Khóa học"}</span>{slug && <><span aria-hidden="true">/</span><span>{slug}</span></>}</div>
        <section className={styles.hero}>
          <div className={styles.copy}>
            <p className={styles.eyebrow}>{page.eyebrow}</p>
            <h1>{page.title.split("\n").map((line, index) => <span key={line}>{index === 1 ? <em>{line}</em> : line}<br /></span>)}</h1>
            <p className={styles.description}>{page.description}</p>
          </div>
          {kind === "course-detail" ? <PublicCourseCatalog courseSlug={slug} /> : <div className={styles.card} role="status">
              <div className={styles.cardTop}><span className={styles.infoMark} aria-hidden="true">i</span><span>TRẠNG THÁI DỮ LIỆU</span></div>
              <h2>{page.label}</h2>
              <p>{page.note}</p>
              <div className={styles.cardLinks}>
                <Link href={kind === "branches" ? "/courses" : "/branches"}>{kind === "branches" ? "Xem khóa học" : "Xem cơ sở"}<span aria-hidden="true">→</span></Link>
                <Link href="/">Về trang chủ<span aria-hidden="true">↗</span></Link>
              </div>
            </div>}
        </section>
        {kind === "courses" && (
          <>
            <PublicCourseCatalog />
            <section className={styles.explore} aria-labelledby="course-guide-title">
              <div className={styles.exploreHeading}><p className={styles.eyebrow}>CÁCH CHỌN KHÓA HỌC</p><h2 id="course-guide-title">Bắt đầu từ điều<br /><em>bạn muốn làm được.</em></h2><p>Trước khi xem lịch hoặc học phí, hãy xác định ngôn ngữ sẽ được sử dụng trong tình huống nào.</p></div>
              <div className={styles.guideList}>
                <article><span>01</span><div><h3>Xác định mục tiêu</h3><p>Giao tiếp hàng ngày, học tập hay công việc?</p></div></article>
                <article><span>02</span><div><h3>Ước lượng trình độ</h3><p>Bắt đầu mới hay tiếp tục từ nền tảng đã có?</p></div></article>
                <article><span>03</span><div><h3>Đối chiếu lịch và cơ sở</h3><p>Chỉ chọn lớp sau khi dữ liệu chính thức được cập nhật.</p></div></article>
              </div>
            </section>
            <section className={styles.courseNote}><span className={styles.noteIndex}>GHI CHÚ</span><div><h2>Thông tin được tổng hợp từ dữ liệu site.</h2><p>Danh mục hiển thị môn, cấp độ, học phí chuẩn và số lớp mở theo dữ liệu API. Lịch học chi tiết hoặc đăng ký trực tuyến chưa được cung cấp ở trang công khai.</p><Link href="/programs">Xem các hướng học <span aria-hidden="true">↗</span></Link></div></section>
            <section className={styles.fieldsSection} aria-labelledby="course-fields-title">
              <p className={styles.eyebrow}>THÔNG TIN CẦN CÓ TRƯỚC KHI ĐĂNG KÝ</p>
              <h2 id="course-fields-title">Một khóa học nên cho bạn biết gì?</h2>
              <div className={styles.fieldsGrid}>
                <article><span>01</span><h3>Nội dung và cấp độ</h3><p>Môn học, mục tiêu đầu ra và trình độ phù hợp.</p></article>
                <article><span>02</span><h3>Lịch và cơ sở</h3><p>Thời gian học cùng cơ sở đang tổ chức lớp.</p></article>
                <article><span>03</span><h3>Học phí và điều kiện</h3><p>Chi phí, thời hạn và điều kiện đăng ký được công bố.</p></article>
              </div>
            </section>
            <section className={styles.faqSection} aria-labelledby="course-faq-title">
              <div><p className={styles.eyebrow}>HỎI ĐÁP</p><h2 id="course-faq-title">Trước khi chọn lớp</h2></div>
              <div className={styles.faqList}>
                <details><summary>Hiện có lớp nào đang mở không?</summary><p>Số lớp đang mở sẽ hiển thị theo từng cơ sở khi API trả về. Nếu chưa có dữ liệu hoặc site bị thiếu, trạng thái sẽ được ghi rõ.</p></details>
                <details><summary>Tôi nên bắt đầu từ trình độ nào?</summary><p>Đối chiếu trình độ hiển thị ở từng khóa học với kinh nghiệm hiện tại. Nếu chưa chắc, ghi lại mục tiêu và lịch phù hợp để trao đổi qua kênh chính thức.</p></details>
                <details><summary>Thông tin học phí lấy từ đâu?</summary><p>Học phí sẽ hiển thị theo dữ liệu do hệ thống xác nhận; trang không tự điền mức giá mẫu.</p></details>
              </div>
            </section>
          </>
        )}
        {kind === "courses" && (
          <section className={styles.contactSection} aria-labelledby="course-contact-title">
            <div>
              <p className={styles.eyebrow}>BƯỚC TIẾP THEO</p>
              <h2 id="course-contact-title">Muốn hỏi lịch học trước khi đăng ký?</h2>
              <p>Gửi chương trình và cơ sở bạn quan tâm để trung tâm tiếp nhận yêu cầu tư vấn.</p>
            </div>
            <Link href="/contact">Gửi yêu cầu tư vấn <span aria-hidden="true">→</span></Link>
          </section>
        )}
        <div className={styles.bottomLine}><span>TRUNG TÂM ĐÀO TẠO NGOẠI NGỮ</span><span>THÔNG TIN CHỈ HIỂN THỊ KHI ĐƯỢC API XÁC NHẬN</span></div>
      </main>
      <WebFooter />
    </div>
  );
}
