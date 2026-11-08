import styles from "./FAQSection.module.scss";

const questions = [
  { question: "Tôi có thể tự đăng ký tài khoản học viên trên website không?", answer: "Hiện tại hệ thống chưa mở tài khoản hoặc cổng đăng ký dành cho học viên. Tài khoản nội bộ được cấp theo quy trình của trung tâm." },
  { question: "Tôi có thể thanh toán học phí trực tuyến không?", answer: "Thanh toán trực tuyến chưa được bật. Thông tin và trạng thái thanh toán chỉ được xác nhận qua quy trình của trung tâm." },
  { question: "Làm sao để xem khóa học và lịch đang mở?", answer: "Danh mục công khai đang chờ kết nối API. Trang khóa học sẽ hiển thị thông tin khi dữ liệu được cung cấp từ hệ thống." },
];

export default function FAQSection() {
  return (
    <section className={styles.section} aria-labelledby="faq-title">
      <div className={styles.inner}>
        <div className={styles.heading}>
          <p className={styles.eyebrow}>THÔNG TIN CẦN BIẾT</p>
          <h2 id="faq-title">Rõ ràng ngay<br />từ bước đầu.</h2>
          <p>Những câu trả lời về cách sử dụng website hiện tại.</p>
        </div>
        <div className={styles.list}>
          {questions.map((item, index) => (
            <details className={styles.item} key={item.question}>
              <summary><span className={styles.index}>0{index + 1}</span><span>{item.question}</span><span className={styles.toggle} aria-hidden="true" /></summary>
              <p>{item.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
