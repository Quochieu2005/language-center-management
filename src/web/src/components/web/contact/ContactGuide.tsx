import Link from "next/link";
import styles from "./ContactGuide.module.scss";

const preparationPoints = [
  {
    title: "Mục tiêu học tập",
    description: "Bạn muốn giao tiếp tự tin hơn, dùng ngoại ngữ trong công việc hay ôn thi chứng chỉ?",
  },
  {
    title: "Trình độ hiện tại",
    description: "Chia sẻ điều bạn đã học hoặc cho biết nếu bạn muốn bắt đầu từ cơ bản.",
  },
  {
    title: "Thời gian phù hợp",
    description: "Nêu những ngày hoặc khung giờ bạn thường có thể tham gia lớp học.",
  },
];

export default function ContactGuide() {
  return (
    <section className={styles.guide} aria-labelledby="contact-guide-title">
      <div className={styles.intro}>
        <p className={styles.eyebrow}>Chuẩn bị tư vấn</p>
        <h2 id="contact-guide-title">Để buổi trao đổi đi thẳng vào điều bạn cần</h2>
        <p>Chia sẻ thêm vài thông tin để trung tâm hiểu nhu cầu học của bạn.</p>
      </div>

      <ul className={styles.points}>
        {preparationPoints.map((point) => (
          <li className={styles.point} key={point.title}>
            <h3>{point.title}</h3>
            <p>{point.description}</p>
          </li>
        ))}
      </ul>

      <section className={styles.resources} aria-labelledby="contact-resources-title">
        <div>
          <h2 id="contact-resources-title">Muốn tìm hiểu trước về chương trình?</h2>
          <p>Xem danh sách khóa học hoặc câu trả lời cho những câu hỏi thường gặp.</p>
        </div>
        <div className={styles.resourceLinks}>
          <Link href="/courses">Xem chương trình khóa học <span aria-hidden="true">→</span></Link>
          <Link href="/#faq">Câu hỏi thường gặp <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </section>
  );
}
