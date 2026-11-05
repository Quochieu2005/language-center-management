import Link from "next/link";
import styles from "./ProgramSection.module.scss";

const themes = [
  { number: "01", title: "Xây nền tảng", detail: "Làm quen phát âm, từ vựng và cấu trúc câu theo từng bước.", tag: "BẮT ĐẦU" },
  { number: "02", title: "Tăng phản xạ giao tiếp", detail: "Tập trung vào nghe, nói và những tình huống thường gặp.", tag: "THỰC HÀNH" },
  { number: "03", title: "Dùng ngôn ngữ theo mục tiêu", detail: "Xác định kỹ năng bạn muốn cải thiện trong học tập hoặc công việc.", tag: "CÁ NHÂN HÓA" },
];

export default function ProgramSection() {
  return (
    <section className={styles.section} aria-labelledby="program-title">
      <div className={styles.inner}>
        <div className={styles.heading}>
          <div><p className={styles.eyebrow}>CHỌN HƯỚNG ĐI</p><h2 id="program-title">Một mục tiêu,<br /><span>một lộ trình rõ ràng.</span></h2></div>
          <p>Các nhóm dưới đây giúp bạn hình dung hướng học. Chương trình và lớp đang mở sẽ chỉ được xác nhận khi danh mục chính thức có dữ liệu.</p>
        </div>
        <div className={styles.grid}>
          {themes.map((theme) => <article className={styles.card} key={theme.number}><span className={styles.tag}>{theme.tag}</span><span className={styles.number}>{theme.number}</span><h3>{theme.title}</h3><p>{theme.detail}</p><span className={styles.rule} /></article>)}
        </div>
        <div className={styles.foot}><span>ĐỊNH HƯỚNG HỌC TẬP · KHÔNG PHẢI DANH SÁCH LỚP ĐANG MỞ</span><Link href="/programs">Khám phá chương trình <span aria-hidden="true">↗</span></Link></div>
      </div>
    </section>
  );
}
