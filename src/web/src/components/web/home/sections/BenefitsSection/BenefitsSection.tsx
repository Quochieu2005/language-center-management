import styles from "./BenefitsSection.module.scss";

const steps = [
  { number: "01", title: "Bắt đầu từ mục tiêu", body: "Bạn muốn sử dụng ngôn ngữ mới trong công việc, học tập hay những cuộc trò chuyện thường ngày?" },
  { number: "02", title: "Chọn nhịp học", body: "Thời gian và lịch sinh hoạt của bạn sẽ giúp thu hẹp những lựa chọn phù hợp." },
  { number: "03", title: "Đi từng bước nhỏ", body: "Một buổi học tốt bắt đầu từ điều vừa sức, rồi dần mở rộng qua thực hành." },
];

export default function BenefitsSection() {
  return (
    <section id="approach" className={styles.section} aria-labelledby="approach-title">
      <div className={styles.inner}>
        <div className={styles.heading}>
          <p className={styles.eyebrow}>MỘT KHỞI ĐẦU CÓ CHỦ ĐÍCH</p>
          <h2 id="approach-title">Học tốt hơn khi<br /><em>bắt đầu đúng câu hỏi.</em></h2>
          <p>Trước khi chọn lớp, hãy nghĩ về cách bạn muốn dùng ngôn ngữ đó. Câu trả lời sẽ giúp bạn chọn hướng đi phù hợp hơn.</p>
        </div>
        <div className={styles.steps}>
          {steps.map((step) => (
            <article className={styles.step} key={step.number}>
              <span className={styles.number}>{step.number}</span>
              <div><h3>{step.title}</h3><p>{step.body}</p></div>
              <span className={styles.arrow} aria-hidden="true">↗</span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
