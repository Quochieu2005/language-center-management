import styles from "./HomePage.module.scss";

const platformParts = [
  {
    label: "Giao diện",
    value: "Next.js App Router và TypeScript",
  },
  {
    label: "Thành phần và kiểu dáng",
    value: "Ant Design, Tailwind CSS và SCSS Modules",
  },
  {
    label: "Kết nối nghiệp vụ",
    value: "Frontend gọi Django API; không kết nối SQL Server trực tiếp",
  },
  {
    label: "Dữ liệu",
    value: "Mỗi cơ sở dùng CSDL SQL Server riêng theo thiết kế phân tán",
  },
];

export default function HomePage() {
  return (
    <main className={styles.page}>
      <div className={styles.content}>
        <p className={styles.eyebrow}>Khởi tạo frontend</p>
        <h1>Quản lý trung tâm đào tạo ngoại ngữ</h1>
        <p className={styles.lead}>
          Dự án Next.js đã sẵn sàng. Đây là màn hình khởi tạo dành cho nhóm phát
          triển; các trang nghiệp vụ sẽ được xây theo đặc tả UI/UX và hợp đồng API.
        </p>

        <section className={styles.setup} aria-labelledby="setup-title">
          <div className={styles.setupHeader}>
            <p className={styles.eyebrow}>Nền tảng</p>
            <h2 id="setup-title">Các phần đã được cấu hình</h2>
          </div>
          <dl className={styles.parts}>
            {platformParts.map((part) => (
              <div className={styles.part} key={part.label}>
                <dt>{part.label}</dt>
                <dd>{part.value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <div className={styles.nextStep}>
          <span className={styles.statusMark} aria-hidden="true" />
          <p>
            Chạy giao diện bằng <code>npm run dev</code> trong thư mục frontend.
          </p>
        </div>
      </div>
    </main>
  );
}
