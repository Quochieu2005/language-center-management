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

## Kiểm tra

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
