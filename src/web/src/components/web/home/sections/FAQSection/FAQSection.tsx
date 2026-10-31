"use client";

import React, { useState } from "react";
import styles from "./FAQSection.module.scss";

interface FAQItem {
  question: string;
  answer: string;
}

const FAQS: FAQItem[] = [
  {
    question: "Tôi có thể chuyển cơ sở học tập giữa Quận 1, Quận 7 và Thủ Đức được không?",
    answer: "Hoàn toàn được. Hệ thống sử dụng cơ chế giao dịch phân tán 2-Phase Commit Coordinator. Khi có nguyện vọng chuyển cơ sở, bạn chỉ cần liên hệ phòng đào tạo tại cơ sở đang học. Toàn bộ hồ sơ điểm danh, bảng điểm quá trình và học phí đã nộp sẽ được điều phối tự động sang cơ sở mới mà không làm gián đoạn lịch học.",
  },
  {
    question: "Khi nhiều học viên cùng đăng ký 1 lớp học sắp đầy chỗ, hệ thống xử lý ra sao?",
    answer: "Hệ thống áp dụng cơ chế Kiểm soát truy cập đồng thời (Concurrency Control) cấp CSDL SQL Server tại site tương ứng. Khi có hai học viên cùng nhấn nút ghi danh vào suất cuối cùng, hệ thống sẽ tuần tự hóa giao dịch bằng khóa bản ghi: đúng một yêu cầu thành công, yêu cầu còn lại được thông báo lớp đã đủ sĩ số và gợi ý lớp tương đương khác, tuyệt đối không để vượt sức chứa phòng học.",
  },
  {
    question: "Học phí và chính sách ưu đãi có giống nhau giữa 3 cơ sở không?",
    answer: "Có. Danh mục môn học, đơn giá học phí và các chương trình ưu đãi được quản lý bởi Ban Giám đốc và nhân bản (Replication) thời gian thực tới toàn bộ các site Q1, Q7 và TD. Bạn đăng ký ở bất kỳ cơ sở nào cũng đều nhận được mức học phí chuẩn niêm yết công khai.",
  },
  {
    question: "Tôi có được thi thử và kiểm tra trình độ đầu vào miễn phí không?",
    answer: "Trung tâm tổ chức kiểm tra trình độ xếp lớp hoàn toàn miễn phí cho cả 4 kỹ năng (Nghe - Nói - Đọc - Viết). Bạn có thể đăng ký thi thử trực tiếp tại bất kỳ phòng Lab nào của 3 cơ sở hoặc đặt lịch làm bài kiểm tra trực tuyến trên hệ thống.",
  },
  {
    question: "Sau khi hoàn thành khóa học, chứng chỉ của tôi có giá trị tra cứu trên toàn hệ thống không?",
    answer: "Tất cả bảng điểm và chứng chỉ tốt nghiệp khóa học đều được cấp mã định danh duy nhất (ví dụ: Q1-HV-000123) và lưu trữ bảo mật. Bạn hoặc nhà tuyển dụng có thể tra cứu tính xác thực của chứng chỉ tại bất kỳ cơ sở nào trong 3 chi nhánh hoặc qua cổng tra cứu của trung tâm.",
  },
  {
    question: "Tôi là người đi làm, nếu bận công tác có được học bù ở cơ sở khác không?",
    answer: "Được. Nhờ tính năng đồng bộ lịch học và giáo trình chuẩn giữa các cơ sở, nếu lớp học tại cơ sở chính của bạn trùng với ngày công tác, bạn có thể xin giấy phép học bù tại lớp có cùng tiến độ bài giảng ở cơ sở Q1, Q7 hoặc Thủ Đức.",
  },
];

export default function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const toggle = (idx: number) => {
    setOpenIndex(openIndex === idx ? null : idx);
  };

  return (
    <section className={styles.faqSection} id="faq">
      <div className={styles.faqInner}>
        {/* Section Header */}
        <div className={styles.sectionHeader}>
          <span className={styles.eyebrow}>Giải đáp thắc mắc</span>
          <h2 className={styles.title}>Câu Hỏi Thường Gặp Của Học Viên</h2>
          <p className={styles.description}>
            Mọi thông tin về quy trình đăng ký, chuyển đổi chi nhánh học tập và chính sách đào tạo
            được giải đáp chi tiết dưới đây.
          </p>
        </div>

        {/* FAQs List */}
        <div className={styles.faqList}>
          {FAQS.map((faq, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div
                className={`${styles.faqItem} ${isOpen ? styles.open : ""}`}
                key={idx}
              >
                <button
                  type="button"
                  className={`${styles.faqQuestion} ${isOpen ? styles.open : ""}`}
                  onClick={() => toggle(idx)}
                  aria-expanded={isOpen}
                >
                  <span>{faq.question}</span>
                  <div className={styles.iconToggle}>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>
                {isOpen && <p className={styles.faqAnswer}>{faq.answer}</p>}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
