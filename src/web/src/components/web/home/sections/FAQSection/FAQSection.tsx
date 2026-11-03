"use client";

import React, { useState } from "react";
import styles from "./FAQSection.module.scss";

interface FAQItem {
  question: string;
  answer: string;
}

const FAQS: FAQItem[] = [
  {
    question: "Trung tâm có những cơ sở nào?",
    answer: "Trung tâm có các cơ sở tại Quận 1, Quận 7 và Thủ Đức. Địa chỉ liên hệ được liệt kê ở cuối trang.",
  },
  {
    question: "Làm sao chọn khóa học phù hợp?",
    answer: "Bạn có thể xem các chương trình đang được giới thiệu ở mục Khóa học. Nếu chưa biết nên bắt đầu từ đâu, hãy gửi yêu cầu tư vấn và chọn chương trình bạn đang quan tâm.",
  },
  {
    question: "Tôi xem học phí và lịch học ở đâu?",
    answer: "Học phí được hiển thị trong thông tin khóa học. Để hỏi lịch khai giảng theo cơ sở, bạn có thể gửi yêu cầu ở biểu mẫu Liên hệ cuối trang.",
  },
  {
    question: "Làm sao để nhận tư vấn?",
    answer: "Điền họ tên, số điện thoại, khóa học và cơ sở bạn quan tâm vào biểu mẫu Liên hệ cuối trang. Trung tâm sẽ tiếp nhận thông tin theo quy trình đang áp dụng.",
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
            Một số thông tin cơ bản giúp bạn chọn chương trình và gửi yêu cầu tư vấn.
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
