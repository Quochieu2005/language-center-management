# Web — Quản lý trung tâm đào tạo ngoại ngữ

Frontend dùng Next.js App Router và TypeScript. Đây là một website dùng chung: người dùng đăng nhập tại cùng một điểm vào, sau đó giao diện hiển thị theo vai trò và quyền API trả về.

## Công nghệ

- Next.js App Router, React và TypeScript
- Ant Design cho các thành phần giao diện có hành vi
- Tailwind CSS cho tiện ích cấu trúc khi cần
- SCSS Modules làm cách style chính
- Django API là nơi xử lý nghiệp vụ và kết nối các CSDL SQL Server riêng theo cơ sở

Trình duyệt không kết nối SQL Server trực tiếp và không chứa thông tin đăng nhập database.

## Chạy local

Yêu cầu Node.js 20.9 trở lên. Trong PowerShell, từ thư mục `src/web`:

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Mở `http://localhost:3000`. Khi API Django chạy ở địa chỉ khác, sửa `NEXT_PUBLIC_API_BASE_URL` trong `.env.local`. Không đặt secret, mật khẩu hay chuỗi kết nối SQL Server vào biến `NEXT_PUBLIC_*`.

Lần đầu mở một route bằng `npm run dev` có thể chậm do Next.js biên dịch route theo nhu cầu. So sánh lần mở đầu với lần mở lại; không dùng riêng số đo development để kết luận production. Với trang có dữ liệu, render layout và skeleton trong lúc API xử lý, không để cả trang chờ mọi request. Xem [README chính mục 12](../../README.md#12-tốc-độ-tải-trang-và-dữ-liệu) và [hướng dẫn Development Environment của Next.js](https://nextjs.org/docs/app/guides/local-development).

## Kiểm tra

Đồ án yêu cầu 2–4 site (hiện 3), tối thiểu một phương pháp phân mảnh, một phương pháp replication, một distributed transaction, một tình huống concurrency, một distributed query và đồng bộ dữ liệu. Frontend thể hiện kết quả API, không tự chứng minh các cơ chế SQL Server này. Đọc [yêu cầu chung và kịch bản demo trong README chính](../../README.md#yêu-cầu-chung-áp-dụng-cho-mọi-đề-tài) và [UI spec mục 8.1](../../specs/ui-ux.md#81-trạng-thái-giao-diện-phục-vụ-kiểm-chứng-môn-học).

Ngoài lint/typecheck/build, kiểm tra form đăng ký báo lớp đầy khi thua cạnh tranh chỗ cuối; chuyển cơ sở phân biệt đã duyệt/đang xử lý/hoàn tất; danh mục không báo lưu xong khi còn thiếu bản sao; báo cáo chỉ rõ site chưa phản hồi. Chạy cùng API/DB thật theo từng TC và lưu kết quả. Khóa nút, dữ liệu mock hoặc mở hai tab chưa thay thế bằng chứng concurrency thực sự ở backend.

```powershell
npm run lint
npm run typecheck
npm run build
```

## Cấu trúc source

- `src/app/`: route và layout của Next.js
- `src/components/web/`: trang công khai và xác thực dùng chung
- `src/components/admin/`: trang làm việc nội bộ theo quyền
- `src/components/shared/`: thành phần tái sử dụng
- `src/assets/icons/`: icon component; kiểm tra icon có sẵn trước khi thêm icon mới
- `src/lib/`: client và service gọi Django API
- `src/styles/`: token và style toàn cục

Chi tiết trang, section và quy tắc giao diện nằm trong `../../specs/ui-ux.md`; hợp đồng endpoint nằm trong `../../specs/api.md`.
