"use client";

import React, { useState } from "react";
import styles from "./FinalCTASection.module.scss";

export default function FinalCTASection() {
  const [formData, setFormData] = useState({
    fullName: "",
    phone: "",
    email: "",
    course: "TOEIC",
    branch: "Q1",
  });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.fullName || !formData.phone) return;
    setSubmitted(true);
  };

  const handleReset = () => {
    setSubmitted(false);
    setFormData({
      fullName: "",
      phone: "",
      email: "",
      course: "TOEIC",
      branch: "Q1",
    });
  };

  return (
    <section className={styles.ctaSection} id="consultation">
      <div className={styles.ctaInner}>
        {/* Left Column: Pitch & Value propositions */}
        <div className={styles.ctaPitch}>
          <div className={styles.pitchBadge}>
            <span>Đăng ký nhận ưu đãi kỳ học mới</span>
          </div>

          <h2 className={styles.pitchTitle}>
            Bắt đầu Hành trình Nâng tầm Ngoại ngữ cùng{" "}
            <span>Hệ thống 3 Cơ sở</span>
          </h2>

          <p className={styles.pitchLead}>
            Đăng ký hôm nay để nhận bài kiểm tra năng lực 4 kỹ năng miễn phí tại phòng Lab và tư vấn
            lộ trình cá nhân hóa trực tiếp từ chuyên gia khảo thí.
          </p>

          <ul className={styles.benefitsList}>
            <li>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>Miễn phí 100% bài thi thử phân loại trình độ tại phòng máy</span>
            </li>
            <li>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>Ưu đãi 10% học phí khi đăng ký theo nhóm từ 2 học viên</span>
            </li>
            <li>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>Chính sách chuyển đổi chi nhánh (Q1, Q7, TD) bảo toàn hồ sơ</span>
            </li>
            <li>
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>Cam kết chuẩn đầu ra CEFR bằng hợp đồng đào tạo bằng văn bản</span>
            </li>
          </ul>
        </div>

        {/* Right Column: Interactive Consultation Form */}
        <div className={styles.formBox}>
          {submitted ? (
            <div className={styles.successCard}>
              <div className={styles.successIcon}>
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="28" height="28">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className={styles.successTitle}>Đăng Ký Thành Công!</h3>
              <p className={styles.successText}>
                Cảm ơn bạn <strong>{formData.fullName}</strong>. Chuyên viên tư vấn tại{" "}
                <strong>
                  {formData.branch === "Q1"
                    ? "Cơ sở Quận 1 (Bến Nghé)"
                    : formData.branch === "Q7"
                    ? "Cơ sở Quận 7 (Tân Phú)"
                    : "Cơ sở Thủ Đức (Linh Chiểu)"}
                </strong>{" "}
                sẽ liên hệ số <strong>{formData.phone}</strong> trong vòng 15 phút để xếp lịch thi thử.
              </p>
              <button type="button" className={styles.resetBtn} onClick={handleReset}>
                Gửi thêm yêu cầu tư vấn khác
              </button>
            </div>
          ) : (
            <>
              <h3 className={styles.formTitle}>Đăng Ký Nhận Tư Vấn & Thi Thử</h3>
              <p className={styles.formSub}>Điền thông tin để phòng đào tạo liên hệ xếp lịch kiểm tra xếp lớp.</p>

              <form className={styles.formGrid} onSubmit={handleSubmit}>
                <div className={styles.inputGroup}>
                  <label htmlFor="fullname-input">Họ và tên của bạn *</label>
                  <input
                    id="fullname-input"
                    type="text"
                    required
                    placeholder="Nguyễn Văn A"
                    value={formData.fullName}
                    onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                  />
                </div>

                <div className={styles.rowTwo}>
                  <div className={styles.inputGroup}>
                    <label htmlFor="phone-input">Số điện thoại *</label>
                    <input
                      id="phone-input"
                      type="tel"
                      required
                      placeholder="0912 345 678"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    />
                  </div>

                  <div className={styles.inputGroup}>
                    <label htmlFor="email-input">Địa chỉ Email</label>
                    <input
                      id="email-input"
                      type="email"
                      placeholder="email@example.com"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  </div>
                </div>

                <div className={styles.rowTwo}>
                  <div className={styles.inputGroup}>
                    <label htmlFor="course-select-cta">Khóa học quan tâm</label>
                    <select
                      id="course-select-cta"
                      value={formData.course}
                      onChange={(e) => setFormData({ ...formData, course: e.target.value })}
                    >
                      <option value="TOEIC">TOEIC Đột phá 700+</option>
                      <option value="IELTS">IELTS Cam kết 6.5+</option>
                      <option value="COMM">Giao tiếp Phản xạ Quốc tế</option>
                      <option value="VSTEP">VSTEP B1 - B2</option>
                    </select>
                  </div>

                  <div className={styles.inputGroup}>
                    <label htmlFor="branch-select-cta">Cơ sở đăng ký học</label>
                    <select
                      id="branch-select-cta"
                      value={formData.branch}
                      onChange={(e) => setFormData({ ...formData, branch: e.target.value })}
                    >
                      <option value="Q1">Cơ sở Quận 1 (Bến Nghé)</option>
                      <option value="Q7">Cơ sở Quận 7 (Tân Phú)</option>
                      <option value="TD">Cơ sở Thủ Đức (Linh Chiểu)</option>
                    </select>
                  </div>
                </div>

                <button type="submit" className={styles.submitBtn}>
                  <span>Gửi thông tin tư vấn ngay</span>
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
