/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import WebFooter from "@/components/web/layout/WebFooter";
import WebHeader from "@/components/web/layout/WebHeader";
import BlogContent, { blogHeadings } from "@/components/web/blog/BlogContent";
import ContactRequestForm from "@/components/web/contact/ContactRequestForm";
import type { ArticleCard } from "@/lib/content/publicArticles";
import type { PublicBlogArticle, PublicBlogArticleSummary } from "@/lib/api/blog";
import styles from "./PublicInfoPage.module.scss";

const programs = [
  { number: "01", label: "NỀN TẢNG", title: "Làm quen và xây nền", text: "Tập trung vào phát âm, vốn từ cơ bản và cấu trúc thường dùng." },
  { number: "02", label: "GIAO TIẾP", title: "Tăng sự tự tin khi sử dụng", text: "Luyện nghe nói qua tình huống, hội thoại và thực hành có mục tiêu." },
  { number: "03", label: "THEO MỤC TIÊU", title: "Học cho việc học và công việc", text: "Xác định kỹ năng cần dùng để chọn nội dung và nhịp học phù hợp." },
];

function Shell({ children, title }: { children: React.ReactNode; title: string }) {
  return <div className={styles.page}><WebHeader /><main id="main-content" className={styles.main}><div className={styles.breadcrumb}><Link href="/">Trang chủ</Link><span>/</span><span>{title}</span></div>{children}</main><WebFooter /></div>;
}

export function ProgramsPage() {
  return <Shell title="Chương trình"><section className={styles.hero}><p className={styles.eyebrow}>ĐỊNH HƯỚNG HỌC TẬP</p><h1>Chọn điểm bắt đầu<br /><span>theo điều bạn cần.</span></h1><p className={styles.lead}>Các nhóm mục tiêu dưới đây gợi ý cách suy nghĩ về lộ trình học. Chúng chưa phải danh sách khóa học hay lớp đang tuyển sinh.</p></section><div className={styles.programGrid}>{programs.map((program) => <article className={styles.program} key={program.number}><span>{program.number} / {program.label}</span><h2>{program.title}</h2><p>{program.text}</p></article>)}</div><section className={styles.pathSection}><div><p className={styles.eyebrow}>TRƯỚC KHI CHỌN</p><h2>Một lộ trình tốt bắt đầu<br />từ câu hỏi đúng.</h2></div><div className={styles.pathSteps}><p><b>01</b><span><strong>Bạn muốn sử dụng ngôn ngữ ở đâu?</strong><small>Chọn tình huống gần với mục tiêu hiện tại.</small></span></p><p><b>02</b><span><strong>Bạn có thể dành thời gian khi nào?</strong><small>Nhịp học cần phù hợp lịch sinh hoạt thực tế.</small></span></p><p><b>03</b><span><strong>Bạn đang ở bước nào?</strong><small>Đối chiếu trình độ với chương trình chính thức khi có dữ liệu.</small></span></p></div></section><section className={styles.goalSection}><p className={styles.eyebrow}>THỬ GỌI TÊN MỤC TIÊU</p><div className={styles.goalGrid}><article><span>01 · GIAO TIẾP</span><h3>“Tôi muốn trò chuyện tự tin hơn.”</h3><p>Ghi lại tình huống thường gặp và kỹ năng bạn muốn luyện.</p></article><article><span>02 · HỌC TẬP</span><h3>“Tôi cần đọc hiểu tài liệu.”</h3><p>Xác định loại nội dung và mức độ khó bạn cần xử lý.</p></article><article><span>03 · CÔNG VIỆC</span><h3>“Tôi muốn dùng ngôn ngữ ở nơi làm việc.”</h3><p>Liệt kê các việc cụ thể như viết thư, họp hoặc trao đổi.</p></article></div><small>Ví dụ mục tiêu để tự xác định nhu cầu; không phải tên chương trình hay cam kết đầu ra.</small></section><aside className={styles.notice}><span aria-hidden="true">i</span><div><strong>Danh mục khóa học chưa được kết nối</strong><p>API hiện chưa cung cấp dữ liệu chương trình công khai. Thông tin môn, học phí, lịch và cơ sở sẽ chỉ xuất hiện sau khi có dữ liệu được xác nhận.</p></div><Link href="/courses">Trạng thái khóa học ↗</Link></aside><section className={styles.questionSection}><p className={styles.eyebrow}>CÂU HỎI THƯỜNG GẶP</p><details><summary>Đây có phải danh sách các lớp đang mở?</summary><p>Không. Đây là các nhóm mục tiêu chung để bạn định hình nhu cầu; danh mục lớp chưa được công khai qua API.</p></details><details><summary>Khi nào tôi có thể xem lịch và học phí?</summary><p>Các thông tin đó sẽ hiển thị khi dữ liệu khóa học chính thức được kết nối và xác nhận.</p></details></section><div className={styles.bottomLinks}><span>CHƯA CÓ LỚP CỤ THỂ ĐƯỢC XÁC NHẬN</span><Link href="/contact">Bạn cần tìm hiểu thêm? Liên hệ ↗</Link></div></Shell>;
}

export function BlogPage({ cards }: { cards: ArticleCard[] }) {
  const featured = cards[0];
  if (!featured) return <Shell title="Blog"><section className={styles.hero}><p className={styles.eyebrow}>GHI CHÚ HỌC TẬP</p><h1>Những ý tưởng nhỏ<br /><span>để học đều hơn.</span></h1><p className={styles.lead}>Chưa có bài viết nào được xuất bản.</p></section></Shell>;
  return <Shell title="Blog"><section className={styles.hero}><p className={styles.eyebrow}>GHI CHÚ HỌC TẬP</p><h1>Những ý tưởng nhỏ<br /><span>để học đều hơn.</span></h1><p className={styles.lead}>Bài viết tham khảo về cách bắt đầu, luyện tập và duy trì thói quen học ngoại ngữ.</p></section><Link className={styles.featured} href={`/blog/${featured.slug}`}><div className={styles.featureArt}>{featured.cover ? <img className={styles.coverImg} src={featured.cover} alt="" /> : <><span>GHI CHÚ<br />01</span><i>ĐỌC VÀ THỬ</i></>}</div><div className={styles.featureCopy}><span className={styles.eyebrow}>BÀI VIẾT GỢI Ý · {featured.readingTime}</span><h2>{featured.title}</h2><p>{featured.excerpt}</p><b>Đọc bài viết <span aria-hidden="true">↗</span></b></div></Link><div className={styles.topicBar}><span>CHỦ ĐỀ</span><i>Bắt đầu</i><i>Kỹ năng</i><i>Phương pháp</i><span className={styles.topicNote}>NỘI DUNG THAM KHẢO, KHÔNG PHẢI KẾT QUẢ CAM KẾT</span></div><div className={styles.articleGrid}>{cards.map((article, index) => <article className={styles.articleCard} key={article.slug}><div className={`${styles.art} ${styles[`art${(index % 3) + 1}`]} ${article.cover ? styles.artCover : ""}`} aria-hidden="true">{article.cover ? <img className={styles.coverImg} src={article.cover} alt="" loading="lazy" /> : <><span>{String(index + 1).padStart(2, "0")}</span><i>{article.category}</i></>}</div><div className={styles.articleCopy}><span>{article.category} · {article.readingTime}</span><h2><Link href={`/blog/${article.slug}`}>{article.title}</Link></h2><p>{article.excerpt}</p><Link className={styles.read} href={`/blog/${article.slug}`}>Đọc bài viết <span aria-hidden="true">↗</span></Link></div></article>)}</div><section className={styles.readingGuide}><div><p className={styles.eyebrow}>ĐỌC VÀ THỬ</p><h2>Biến một ý tưởng<br />thành buổi luyện tập.</h2></div><div><p><b>01</b> Chọn một gợi ý phù hợp với mục tiêu hiện tại.</p><p><b>02</b> Thử áp dụng trong một lần học ngắn.</p><p><b>03</b> Ghi lại điều hữu ích và điều cần đổi.</p></div><Link href="/programs">Xem cách xác định mục tiêu ↗</Link></section><p className={styles.editorialNote}>Các bài viết là nội dung biên tập tham khảo; không gắn tác giả, trích dẫn hay số liệu chưa được xác nhận.</p></Shell>;
}

export function ArticlePage({ article, latest = [] }: { article: PublicBlogArticle | null; latest?: PublicBlogArticleSummary[] }) {
  if (!article) return <Shell title="Bài viết"><section className={styles.hero}><p className={styles.eyebrow}>BLOG CHƯA KHẢ DỤNG</p><h1>Chưa tải được<br /><span>bài viết này.</span></h1><p className={styles.lead}>Các cơ sở chưa trả đủ dữ liệu Blog. Hãy thử tải lại sau.</p><Link className={styles.button} href="/blog">Về trang Blog ↗</Link></section></Shell>;
  const headings = blogHeadings(article.content);
  return <Shell title="Blog">
    <div className={styles.articleLayout}>
      <article className={styles.articleMain}>
        <Link className={styles.back} href="/blog">← Tất cả bài viết</Link>
        <h1>{article.title}</h1>
        <p className={styles.lead}>{article.excerpt}</p>
        <div className={styles.articleBody}><BlogContent content={article.content} /></div>
      </article>
      <aside className={styles.articleSide}>
        {headings.length > 0 && <nav className={styles.sideCard} aria-label="Nội dung chính">
          <h2>Nội dung chính</h2>
          <ul>{headings.map((item) => <li key={item.id} className={item.level > 2 ? styles.tocSub : undefined}><a href={`#${item.id}`}>{item.text}</a></li>)}</ul>
        </nav>}
        {latest.length > 0 && <section className={styles.sideCard}>
          <h2>Bài viết mới nhất</h2>
          <ul className={styles.latestList}>{latest.map((item) => <li key={item.slug}><Link href={`/blog/${item.slug}`}><span>{item.category.name} · {item.reading_time_minutes} phút đọc</span><b>{item.title}</b></Link></li>)}</ul>
        </section>}
        <section className={`${styles.sideCard} ${styles.sideCta}`}>
          <h2>Tiếp tục khám phá</h2>
          <p>Xem các hướng học và tình trạng danh mục chương trình tại trung tâm.</p>
          <Link href="/programs">Xem chương trình ↗</Link>
        </section>
      </aside>
    </div>
  </Shell>;
}

export function ContactPage() {
  return <Shell title="Liên hệ">
    <section className={styles.hero}>
      <p className={styles.eyebrow}>LIÊN HỆ TRUNG TÂM</p>
      <h1>Mình có thể<br /><span>giúp bạn tìm gì?</span></h1>
      <p className={styles.lead}>Gửi câu hỏi đến cơ sở bạn muốn trao đổi. Trung tâm sẽ xem yêu cầu và phản hồi qua email.</p>
    </section>
    <ContactRequestForm />
    <div className={styles.contactGrid}>
      <article><span className={styles.contactNumber}>01 / KHÓA HỌC</span><h2>Tìm chương trình phù hợp</h2><p>Khám phá nội dung khóa học trước khi gửi yêu cầu tư vấn.</p><Link href="/courses">Xem khóa học ↗</Link></article>
      <article><span className={styles.contactNumber}>02 / ĐỊA ĐIỂM</span><h2>Chọn cơ sở phụ trách</h2><p>Yêu cầu được lưu tại cơ sở bạn chọn để đội ngũ tại đó phản hồi.</p><Link href="/branches">Xem cơ sở ↗</Link></article>
    </div>
    <section className={styles.contactFaq}>
      <p className={styles.eyebrow}>THÔNG TIN TRÊN WEBSITE</p>
      <details><summary>Yêu cầu được gửi đến đâu?</summary><p>Yêu cầu được lưu trong CSDL riêng của cơ sở bạn chọn và hiển thị trong mục Liên hệ của trang quản trị.</p></details>
      <details><summary>Trung tâm sẽ phản hồi bằng cách nào?</summary><p>Quản trị viên gửi phản hồi từ hộp thư quản trị đến email bạn cung cấp.</p></details>
    </section>
  </Shell>;
}
