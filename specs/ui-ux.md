# Đặc tả UI/UX và cấu trúc giao diện

> Trạng thái: Đặc tả yêu cầu trước khi viết giao diện. Tài liệu này chưa có nghĩa là frontend đã được cài đặt hoặc các màn hình đã hoàn thành.

Tài liệu quy định cách chia component, page, section, SCSS, SVG, nội dung trang công khai, đăng nhập/đăng ký dùng chung, khu vực làm việc theo chức vụ, responsive và cách kiểm tra giao diện. Đây là **một ứng dụng frontend**, không phải mỗi chức vụ một website riêng: người dùng vào cùng địa chỉ, dùng cùng màn hình đăng nhập; sau khi API xác thực, giao diện hiển thị đúng trang và thao tác theo quyền được cấp. Hợp đồng request/response thuộc [`api.md`](api.md); nghiệp vụ và kiến trúc phân tán thuộc [`README.md`](../README.md); cấu trúc bảng thuộc [`docs/DATABASE_SCHEMA.md`](../docs/DATABASE_SCHEMA.md).

## 1. Sản phẩm và nội dung

| Hạng mục | Quy ước cho dự án |
|---|---|
| Sản phẩm | Trung tâm đào tạo ngoại ngữ, có các khóa học và lớp tại từng cơ sở |
| Thương hiệu | Tên thương hiệu chưa được nhóm cung cấp; trong bản phác thảo dùng `[Tên trung tâm]`, không tự đặt tên |
| Cơ sở ban đầu | Quận 1 (Q1), Quận 7 (Q7), Thủ Đức (TD); danh sách hiển thị lấy từ API, không viết cứng trong giao diện |
| Người xem Web | Khách xem khóa học/cơ sở; người dùng nội bộ cũng truy cập cùng website để đăng nhập |
| Người dùng sau đăng nhập | Admin Big, Admin Small, lễ tân, kế toán, giáo viên; cùng frontend nhưng nội dung và thao tác theo quyền API trả về |
| Nỗi băn khoăn dùng cho nội dung | Người học cần so sánh trình độ, lịch và cơ sở để tìm lớp phù hợp; đây là giả định nội dung, không tuyên bố là kết quả khảo sát khách hàng |
| Bằng chứng hiện có | Có ba cơ sở ban đầu theo phạm vi đồ án. Chưa có dữ liệu được xác nhận về số học viên, kết quả thi, tỷ lệ đậu hoặc đánh giá khách hàng |
| Giọng văn | Thực tế, rõ ràng, gần gũi và chuyên nghiệp; câu ngắn, nói việc người học cần làm |

Không dùng các câu sáo rỗng như “Nâng tầm”, “Hàng đầu”, “Đột phá”, “Đồng hành cùng bạn”, “Chinh phục ước mơ”, “Uy tín tạo nên thương hiệu” hoặc văn mẫu trung tâm/bảo hiểm. Không bịa lời chứng thực, điểm số, tỷ lệ thành công, số năm hoạt động, ưu đãi, sĩ số hay số lượng khóa học. Nội dung động phải lấy từ API; thông tin chưa được cung cấp phải ghi `[Cần nhóm xác nhận]` hoặc ẩn khỏi bản phát hành.

## 2. Cấu trúc thư mục component

Component page nghiệp vụ đặt dưới một trong hai nhánh `web` hoặc `admin`. Đăng nhập/đăng ký là luồng chung trước khi biết vai trò nên nằm trong `web/auth`; đây vẫn là một frontend và không tạo một ứng dụng đăng nhập riêng cho từng chức vụ. Trong từng page, các phần lớn của trang được tách thành section riêng; section phức tạp có thư mục và SCSS riêng. Component dùng chung giữa hai khu vực chỉ đặt ở `shared`, không nhân đôi mã hoặc trộn luồng Admin vào trang công khai.

```text
frontend/src/
├── app/                                  # Khai báo route, gọi page component
├── components/
│   ├── web/
│   │   ├── auth/                           # Cùng một cửa vào đăng nhập/đăng ký cho toàn frontend
│   │   │   ├── login/
│   │   │   │   ├── LoginPage.tsx
│   │   │   │   ├── LoginPage.module.scss
│   │   │   │   └── sections/
│   │   │   │       └── LoginForm/
│   │   │   │           ├── LoginForm.tsx
│   │   │   │           └── LoginForm.module.scss
│   │   │   └── register/
│   │   │       ├── RegisterPage.tsx
│   │   │       ├── RegisterPage.module.scss
│   │   │       └── sections/
│   │   │           └── RegisterForm/
│   │   │               ├── RegisterForm.tsx
│   │   │               └── RegisterForm.module.scss
│   │   ├── landing/
│   │   │   ├── LandingPage.tsx
│   │   │   ├── LandingPage.module.scss
│   │   │   └── sections/
│   │   │       ├── HeroSection/
│   │   │       │   ├── HeroSection.tsx
│   │   │       │   └── HeroSection.module.scss
│   │   │       ├── CourseFinderSection/
│   │   │       ├── BenefitsSection/
│   │   │       ├── CoursePreviewSection/
│   │   │       ├── BranchesSection/
│   │   │       ├── ProofSection/
│   │   │       ├── FAQSection/
│   │   │       └── FinalCTASection/
│   │   ├── courses/
│   │   │   ├── CoursesPage.tsx
│   │   │   └── sections/
│   │   ├── course-detail/
│   │   │   ├── CourseDetailPage.tsx
│   │   │   └── sections/
│   │   └── branches/
│   │       ├── BranchesPage.tsx
│   │       └── sections/
│   ├── admin/
│   │   ├── dashboard/
│   │   ├── students/
│   │   ├── enrollments/
│   │   ├── classes/
│   │   ├── tuition/
│   │   ├── grades/
│   │   ├── transfers/
│   │   ├── reports/
│   │   └── accounts/                       # Quản lý tài khoản nội bộ theo quyền
│   └── shared/                            # Nút, trường nhập, trạng thái, dialog dùng chung
├── assets/
│   └── icons/                              # SVG viết bằng component code, dùng lại qua import
└── styles/
    ├── _tokens.scss
    └── globals.scss
```

Đây là cấu trúc đích để thống nhất trước khi scaffold frontend. Mỗi thư mục page của Admin áp dụng cùng quy tắc như `web/landing`: có page component, `sections/` cho các khu vực lớn và một file `*.module.scss` cho từng section cần style riêng. Section nhỏ chỉ tách khi có nội dung, trạng thái hoặc hành vi riêng; không tạo component chỉ để bọc một thẻ HTML đơn giản.

Ví dụ cấu trúc một page Admin:

```text
components/admin/transfers/
├── TransfersPage.tsx
├── TransfersPage.module.scss
└── sections/
    ├── TransferPageHeader/
    │   ├── TransferPageHeader.tsx
    │   └── TransferPageHeader.module.scss
    ├── TransferFilters/
    ├── TransferInboxTable/
    ├── TransferRequestForm/
    └── TransferDetail/
```

Route chỉ lắp page component và xử lý ranh giới điều hướng. Component giao diện gọi API qua lớp client/service thống nhất; không truy cập SQL Server hoặc chứa chuỗi kết nối. Dữ liệu nghiệp vụ không được viết cứng trong component.

## 3. Một frontend dùng chung, giao diện thay đổi theo quyền

### 3.1. Trang công khai và xác thực dùng chung

| Page | Sections chính | Mục tiêu |
|---|---|---|
| Đăng nhập | Nhận diện thương hiệu, form tài khoản/mật khẩu, hiện/ẩn mật khẩu, quên mật khẩu, lỗi và trạng thái đang gửi | Một trang đăng nhập cho mọi chức vụ; không có lựa chọn “đăng nhập Admin Big/Admin Small/giáo viên” để tự quyết định quyền |
| Đăng ký tài khoản | Giới thiệu điều kiện đăng ký, form phù hợp với loại tài khoản được nhóm cho phép, trạng thái gửi thành công/chờ xử lý | Cùng frontend và cùng luồng form; API quyết định loại tài khoản/role. Không cho người dùng tự chọn hoặc tự cấp quyền nội bộ |
| Landing page | Điều hướng chung có liên kết đăng nhập, Hero, tìm khóa học, vấn đề người học, giải pháp/lợi ích, khóa học đang mở, cơ sở, bằng chứng có thật, FAQ, CTA, footer | Giúp người xem hiểu khóa học và tìm bước tiếp theo trong vài giây; người dùng nội bộ luôn có thể vào cùng trang đăng nhập |
| Danh sách khóa học | Tiêu đề, bộ lọc môn/trình độ/cơ sở, danh sách kết quả, phân trang hoặc tải thêm | So sánh khóa học/lớp đang được API trả về |
| Chi tiết khóa học | Mô tả khóa, trình độ, số buổi, học phí chuẩn, lớp/lịch/cơ sở khả dụng, CTA | Hiểu nội dung và điều kiện trước khi liên hệ hoặc đăng ký theo luồng được nhóm chốt |
| Cơ sở | Danh sách cơ sở, địa chỉ/liên hệ nếu có dữ liệu được duyệt, hướng dẫn xem lớp tại cơ sở | Chọn địa điểm học từ dữ liệu cơ sở đang hoạt động |

**Chính sách đăng ký cần bám theo phạm vi hiện tại trong README:** học viên chưa có tài khoản trong phiên bản này; tài khoản nhân viên/giáo viên do Admin Big tạo và phân quyền. Vì vậy, route đăng ký có thể được thiết kế chung trong cấu trúc frontend nhưng chưa được bật như đăng ký tài khoản công khai cho tới khi nhóm chốt nghiệp vụ, API và schema. Nếu sau này mở đăng ký công khai, API phải xác định rõ loại tài khoản được phép tạo; tuyệt đối không nhận `vai_tro`, chức vụ, cơ sở hoặc phạm vi quyền do trình duyệt tự chọn làm nguồn cấp quyền. CTA công khai mặc định là **“Xem khóa học”** hoặc **“Xem cơ sở”**; mọi CTA dẫn tới thao tác chưa có API phải được đánh dấu chờ thống nhất.

### 3.2. Khu vực làm việc sau đăng nhập

Đây là khu vực trong cùng website, không phải frontend riêng theo chức vụ. Tất cả người dùng nội bộ đi qua cùng màn hình đăng nhập; Django/API xác thực tài khoản rồi trả về ngữ cảnh cần cho giao diện: chức vụ/vai trò, cơ sở được giao (nếu có), phạm vi lớp (nếu là giáo viên) và quyền thao tác. Frontend dùng ngữ cảnh đó để điều hướng tới trang đầu phù hợp và dựng menu theo quyền. Không có dropdown cho người dùng tự chọn chức vụ lúc đăng nhập.

| Page | Sections chính | Quyền và cách lấy dữ liệu |
|---|---|---|
| Trang tổng quan | Tiêu đề/ngữ cảnh cơ sở, công việc cần xử lý, chỉ số nghiệp vụ, cảnh báo site | Admin Big xem toàn hệ thống; Admin Small xem site được gán; các chức vụ khác chỉ thấy thông tin cần cho công việc được giao; thiếu site phải báo rõ |
| Học viên | Tìm kiếm/bộ lọc, danh sách, thông tin hồ sơ, lịch sử liên quan | Site Router định tuyến theo phạm vi; không suy site chỉ từ tiền tố mã |
| Đăng ký và xếp lớp | Chọn học viên/lớp, danh sách đăng ký, chi tiết đăng ký, đổi lớp | `LOCAL`; kiểm tra học viên và lớp cùng cơ sở, chỗ còn lại và trạng thái lớp |
| Học phí | Số phải thu/đã thu, lịch sử phiếu thu, form thu/hoàn | `LOCAL`; phiếu đã phát sinh không có nút xóa |
| Điểm | Chọn lớp, danh sách học viên, nhập/sửa điểm, lịch sử thay đổi | `LOCAL`; giáo viên chỉ thấy lớp được phân công |
| Chuyển cơ sở | Form đề nghị cho Admin Small; hộp thư/chi tiết/duyệt/từ chối cho Admin Big; theo dõi trạng thái | Đề nghị `LOCAL` ở nguồn, hộp thư `GLOBAL`, giao dịch nguồn-đích chỉ chạy sau duyệt |
| Báo cáo | Bộ lọc theo site/thời gian/trạng thái, bảng hoặc biểu đồ, trạng thái đầy đủ dữ liệu | Admin Small chỉ site mình; Admin Big dùng `GLOBAL` và thấy cảnh báo khi thiếu site; lễ tân/kế toán/giáo viên chỉ thấy báo cáo được cấp |
| Tài khoản và phân quyền | Danh sách/tạo/khóa tài khoản, phân công cơ sở và chức vụ | Theo README, Admin Big quản lý tài khoản nội bộ; màn hình và thao tác chỉ xuất hiện cho người có quyền |

| Chức vụ | Trang/thao tác được thể hiện trên cùng frontend |
|---|---|
| Admin Big | Khu vực quản trị toàn hệ thống: cơ sở, tài khoản/phân công, danh mục dùng chung, thống kê toàn cục và duyệt/từ chối đề nghị chuyển cơ sở |
| Admin Small | Khu vực quản trị site được giao: nghiệp vụ tại cơ sở, tạo đề nghị chuyển học viên, theo dõi đề nghị; không duyệt đề nghị và không truy cập site khác |
| Lễ tân | Hồ sơ học viên, đăng ký khóa học, xếp/đổi lớp trong một site được giao |
| Kế toán | Học phí, phiếu thu/hoàn và công nợ trong một site được giao |
| Giáo viên | Các lớp/buổi được phân công; điểm danh và nhập/sửa điểm theo quyền |
| Học viên | Chưa đăng nhập trong phạm vi hiện tại theo README; chỉ bổ sung màn hình học viên sau khi nhóm thống nhất lại phạm vi |

Các chức vụ dùng chung shell, điều hướng, biểu mẫu và component khi phù hợp; menu và nội dung được dựng theo quyền API trả về. Ẩn nút hoặc chặn route ở frontend chỉ cải thiện trải nghiệm, không thay thế việc Django/API kiểm tra quyền ở mọi request. Nếu người dùng mở URL không thuộc quyền, hiển thị trang “Bạn không có quyền truy cập” và đường quay về trang được phép; nếu phiên hết hạn, yêu cầu đăng nhập lại.

### 3.3. Luồng đăng nhập, đăng ký và phân quyền giao diện

1. Mọi chức vụ mở cùng route đăng nhập và gửi thông tin tới API; frontend không hỏi người dùng muốn vào vai trò nào.
2. API xác thực tài khoản, trạng thái hoạt động và quyền; mật khẩu không được lưu ở trình duyệt hoặc ghi ra log. API là nơi quyết định vai trò, chức vụ, site và phạm vi lớp.
3. Sau đăng nhập thành công, frontend đọc ngữ cảnh phiên do API cung cấp và mở trang tổng quan phù hợp. Admin Big thấy menu toàn hệ thống; Admin Small thấy menu site được giao; lễ tân, kế toán và giáo viên thấy menu theo nhiệm vụ.
4. Các API nghiệp vụ vẫn phải kiểm tra quyền và site ở phía máy chủ. Frontend không được dùng giá trị site từ URL/local storage để cấp quyền hoặc truy vấn thẳng cơ sở dữ liệu.
5. Đăng xuất xóa phiên phía client theo cơ chế API quy định. Lỗi đăng nhập dùng thông báo chung, không tiết lộ tài khoản có tồn tại hay không. Đăng ký công khai vẫn tắt cho tới khi nhóm thống nhất đối tượng được đăng ký và cập nhật README/API/schema cho khớp.

### 3.4. Section dự kiến bên trong từng page

Mỗi section lớn nằm trong thư mục riêng bên trong page, tối thiểu gồm component và `*.module.scss`. Tên dưới đây là cấu trúc ban đầu để nhóm chia việc; có thể gộp/tách khi thiết kế chi tiết nhưng không được đưa toàn bộ màn hình vào một file lớn.

| Page | Section folders dự kiến |
|---|---|
| Web — Login | `LoginIntro`, `LoginForm`, `ForgotPasswordLink`, `AuthFeedback` |
| Web — Register | `RegisterIntro`, `RegisterForm`, `RegistrationNotice`, `AuthFeedback` |
| Web — Landing | `HeroSection`, `CourseFinderSection`, `BenefitsSection`, `CoursePreviewSection`, `BranchesSection`, `ProofSection`, `FAQSection`, `FinalCTASection` |
| Web — Courses | `CoursePageHeader`, `CourseFilters`, `CourseResults`, `CoursePagination`, `CourseEmptyState` |
| Web — Course detail | `CourseOverview`, `CourseFacts`, `AvailableClasses`, `CourseCTA` |
| Web — Branches | `BranchPageHeader`, `BranchList`, `BranchContact`, `BranchMap` (chỉ khi có địa chỉ/toạ độ đã xác minh) |
| Admin — Dashboard | `DashboardHeader`, `SiteSummary`, `PendingTasks`, `OperationalAlerts` |
| Admin — Students | `StudentPageHeader`, `StudentFilters`, `StudentTable`, `StudentProfile`, `StudentEmptyState` |
| Admin — Enrollments | `EnrollmentFilters`, `EnrollmentTable`, `EnrollmentForm`, `EnrollmentDetail` |
| Admin — Classes | `ClassFilters`, `ClassTable`, `ClassAssignmentForm`, `ClassCapacity` |
| Admin — Tuition | `TuitionSummary`, `PaymentHistory`, `CollectPaymentForm`, `RefundForm` |
| Admin — Grades | `GradeClassPicker`, `StudentGradeTable`, `GradeEditor`, `GradeChangeHistory` |
| Admin — Transfers | `TransferRequestForm`, `TransferInbox`, `TransferFilters`, `TransferDetail`, `TransferDecision` |
| Admin — Reports | `ReportFilters`, `StudentSummary`, `StudentResults`, `IncompleteSiteNotice` |
| Admin — Account management | `AccountPageHeader`, `AccountFilters`, `AccountTable`, `AccountForm`, `RoleAndSiteAssignment` |

Nếu một section chỉ là một tiêu đề hoặc đoạn text không có style/hành vi riêng thì không cần tách thêm component. Các mẫu loading/empty/error dùng chung nên import từ `components/shared`, nhưng nội dung phải nói đúng nghiệp vụ của page.

## 4. Nội dung và layout Landing Page

### Thông điệp đang dùng làm bản nháp

- **Hook:** “Chưa rõ nên bắt đầu với lớp ngoại ngữ nào?”
- **Câu hỗ trợ:** “Xem khóa học theo trình độ, lịch học và cơ sở. Chọn thông tin phù hợp rồi mới quyết định bước tiếp theo.”
- **CTA chính:** “Xem khóa học” → trang danh sách khóa học.
- **CTA phụ:** “Chọn cơ sở” → danh sách cơ sở.
- **Problem:** Người học cần biết lớp có đúng trình độ, lịch và địa điểm phù hợp trước khi đăng ký. Trình bày như nhu cầu phổ biến, không khẳng định đây là kết quả khảo sát.
- **Solution:** Cho phép xem khóa học/lớp theo môn, trình độ, lịch và cơ sở — chỉ bật bộ lọc khi API có dữ liệu tương ứng.
- **Benefits:** Người xem so sánh được nội dung, số buổi, học phí chuẩn và lớp đang mở trước khi liên hệ; không hứa tiết kiệm một số giờ hoặc đảm bảo kết quả học tập.
- **Proof:** Dùng dữ liệu thật được phép công khai như khóa học và cơ sở đang hoạt động. Chỉ dùng đánh giá học viên, kết quả thi hoặc con số khi nhóm cung cấp nguồn và xác nhận quyền sử dụng.
- **CTA cuối:** “Tìm khóa học phù hợp” hoặc “Xem cơ sở”; không dùng CTA đăng ký trực tuyến nếu luồng đó chưa được API hỗ trợ.

Tên trung tâm, địa chỉ, hotline, học phí đang áp dụng, ưu đãi, ảnh lớp học và lời nhận xét chưa được xác nhận trong tài liệu dự án. Không tự điền giá trị giả; dùng nội dung chờ duyệt hoặc lấy dữ liệu từ API.

### Thứ tự section và visual gợi ý

| Section | Nội dung cần đọc nhanh | Visual gợi ý |
|---|---|---|
| Hero / Hook | Nêu ngay băn khoăn chọn lớp; CTA “Xem khóa học” và “Chọn cơ sở” | Bố cục lệch nhẹ: headline lớn một phía, phía còn lại là khối tìm khóa học/lịch/cơ sở; dùng ảnh thật đã được duyệt nếu có |
| Tìm khóa học | Chọn môn, trình độ, cơ sở hoặc lịch theo dữ liệu API | Bộ lọc gọn, ưu tiên thao tác; không cần biến thành dãy thẻ đồng đều |
| Vấn đề người học | Nêu các tiêu chí khó so sánh: lớp, lịch, cơ sở, học phí | Typography và khoảng trắng; tránh stock photo minh họa cảm xúc giả |
| Giải pháp / lợi ích | Giải thích cách xem thông tin trước khi chọn lớp | Một luồng ngắn hoặc ví dụ giao diện thật; chỉ mô tả tính năng có trong API |
| Khóa học đang mở | Hiển thị khóa/lớp, trình độ, lịch, cơ sở, học phí được phép công khai | Danh sách có phân cấp; có thể làm nổi bật một nhóm nội dung thay vì các card giống nhau |
| Cơ sở | Q1, Q7, TD và địa chỉ/liên hệ khi dữ liệu đã được xác minh | Bản đồ hoặc ảnh cơ sở thật; không đặt điểm giả trên bản đồ |
| Bằng chứng | Lời nhận xét hoặc số liệu có nguồn, ngày và quyền sử dụng | Trích dẫn có người/nguồn thật; nếu chưa có bằng chứng, ẩn section hoặc thay bằng thông tin khóa học/cơ sở đã xác minh |
| FAQ | Trả lời câu hỏi về trình độ, lịch, học phí, cơ sở theo dữ liệu đã chốt | Accordion có trạng thái mở/đóng rõ ràng |
| CTA cuối và footer | Nhắc lại hành động kế tiếp, địa chỉ/liên hệ đã xác minh | Bố cục gọn, không lặp banner khuyến mãi không có dữ liệu |

### Bản copy đề xuất cho Landing Page

Đây là bản nháp theo bối cảnh trung tâm ngoại ngữ, không phải nội dung đã được thương hiệu duyệt. Chỉ đưa các trường động lên trang khi API trả về và nhóm xác nhận được phép công khai.

| Section | Nội dung copy đề xuất | CTA / visual |
|---|---|---|
| Hero | **Tiêu đề:** “Tìm lớp ngoại ngữ hợp với trình độ và thời gian của bạn.” **Mô tả:** “Xem khóa học, số buổi, lịch học và cơ sở trước khi chọn lớp.” | “Xem khóa học” và “Chọn cơ sở”. Visual: headline lớn, cạnh đó là bộ lọc khóa học; không dùng ảnh stock làm bằng chứng |
| Vấn đề | **Tiêu đề:** “Chọn lớp cần nhiều hơn một cái tên khóa học.” **Mô tả:** “Trình độ, số buổi, lịch và địa điểm đều ảnh hưởng đến việc chọn lớp. Hãy xem các thông tin đó trước khi quyết định.” | Typography và khoảng trắng; không dùng câu khẳng định đây là khảo sát thực tế |
| Giải pháp | **Tiêu đề:** “Đặt thông tin quan trọng cạnh nhau.” **Mô tả:** “Xem môn học, trình độ, số buổi và các lớp theo cơ sở trên cùng một nơi.” | Visual: một danh sách khóa học/lớp thật do API trả về; nếu API chưa có bộ lọc thì không mô phỏng bộ lọc hoạt động |
| Lợi ích | **Trình độ:** “Biết khóa học dành cho cấp độ nào.” **Lịch và cơ sở:** “So thời gian học với địa điểm trước khi chọn.” **Học phí:** “Xem học phí chuẩn trước khi tìm hiểu bước tiếp theo.” | Dùng ba khối nội dung có kích thước/phân cấp khác nhau, không lặp ba card giống hệt nhau. Chỉ hiển thị học phí và lịch được API xác nhận |
| Khóa học | **Tiêu đề:** “Các khóa học đang được mở.” **Mô tả:** “Xem trình độ, số buổi và lớp hiện có theo cơ sở.” | Visual: một nội dung nổi bật kèm danh sách phụ. Chỉ coi lớp là đang mở khi trạng thái từ API cho phép đăng ký |
| Cơ sở | **Tiêu đề:** “Chọn nơi học phù hợp với lịch của bạn.” **Mô tả:** “Xem các cơ sở đang hoạt động và lớp được mở tại từng nơi.” | Visual: danh sách/vị trí theo dữ liệu thật của `CoSo`; không giả lập địa chỉ hoặc bản đồ |
| Bằng chứng | **Tiêu đề:** “Thông tin để bạn tự đối chiếu.” **Mô tả:** “Xem trình độ, số buổi, lịch và học phí chuẩn của khóa học trước khi chọn.” | Đây là nội dung thay thế an toàn khi chưa có review. Chỉ thay bằng lời nhận xét/kết quả thật khi có nguồn, ngày và quyền sử dụng |
| FAQ | **Tiêu đề:** “Cần biết thêm trước khi chọn lớp?” **Câu hỏi gợi ý:** “Khóa học dành cho trình độ nào?”, “Lịch học và cơ sở được xem ở đâu?”, “Học phí hiển thị là học phí nào?” | Accordion; câu trả lời phải khớp dữ liệu/schema và API đã thống nhất |
| CTA cuối | **Tiêu đề:** “Bắt đầu từ khóa học bạn đang tìm.” **Mô tả:** “Xem danh sách khóa học và chọn cơ sở để kiểm tra các lớp hiện có.” | Nút “Xem khóa học”. Footer dùng tên, địa chỉ, điện thoại và giờ làm việc đã được nhóm xác minh |

Không dùng “Social Proof” giả để lấp chỗ trống. Khi nhóm chưa có đánh giá hoặc số liệu có thể kiểm chứng, section chỉ trình bày thông tin khóa học/cơ sở ở trên; không đặt tên mục là “Học viên nói gì” nếu chưa có lời nhận xét thật.

### Hướng bố cục

Thiết kế có bất đối xứng nhẹ và khoảng thở lớn: hero ưu tiên headline và công cụ tìm lớp; phần khóa học có thể dùng danh sách biên tập hoặc một mục nổi bật kèm danh sách phụ. Không xếp mọi section thành cùng một lưới card. Căn lề trái cho nội dung chính, dùng độ rộng dòng dễ đọc; chỉ căn giữa cho CTA ngắn hoặc thông báo cần tập trung.

## 5. Hệ thống màu, chữ và thư viện giao diện

### Màu và typography

Giới hạn **ba màu gốc** cho toàn sản phẩm; dùng độ đậm/opacity của chính ba màu này để tạo phân cấp, không thêm các màu trang trí khác:

| Token đề xuất | Mã màu | Dùng cho |
|---|---|---|
| `ink` | `#1D2926` | Chữ chính, đường viền cần tương phản, biểu tượng |
| `paper` | `#F6F5F0` | Nền tổng thể và bề mặt sáng |
| `petrol` | `#2C746B` | CTA, liên kết, trạng thái đang chọn và điểm nhấn |

Đây là palette đề xuất để bắt đầu, có thể đổi mã trước khi chốt theme nhưng vẫn giữ giới hạn ba màu. Trạng thái lỗi/cảnh báo/thành công không chỉ dựa vào màu: phải có icon, nhãn và thông báo chữ. Theme Ant Design cần override màu mặc định để không tự thêm xanh dương/đỏ/xanh lá ngoài palette.

Dùng sans-serif gọn như **Inter** với fallback `system-ui, sans-serif`; ưu tiên font tự lưu hoặc cơ chế tối ưu của framework, không chặn render để tải font từ dịch vụ bên ngoài. Phân cấp chữ rõ: tiêu đề editorial lớn, tiêu đề section, nội dung, nhãn/trợ giúp. Admin ưu tiên khả năng quét bảng và biểu mẫu hơn kích thước headline.

### Ant Design, Tailwind và SCSS

- Dùng Ant Design cho thành phần có hành vi/phức tạp như Form, Select, Table, Drawer, Modal, Pagination và thông báo; cấu hình theme để đồng nhất palette, radius, chiều cao control và focus state.
- SCSS Modules là nguồn style chính: mỗi page/section/component có `*.module.scss`; token chung nằm ở `styles/_tokens.scss`, style nền và reset ở `styles/globals.scss`.
- Tailwind được phép dùng cho tiện ích cấu trúc đơn giản khi cần. Không lặp chuỗi utility class dài ở nhiều nơi; không style cùng một thuộc tính bằng cả Tailwind và SCSS. Tách biến thể thành component hoặc class SCSS có tên nghĩa.
- Component tái sử dụng gồm nhóm phù hợp như `Button`, `FormField`, `PageHeader`, `SiteBadge`, `LoadingState`, `EmptyState`, `ErrorState`, `ConfirmDialog` và trạng thái thiếu dữ liệu toàn cục. Không tạo abstraction chung nếu Web và Admin thật sự có hành vi khác nhau.
- Tránh import toàn bộ thư viện icon hoặc thư viện nặng nếu chỉ dùng vài thành phần; chỉ nạp component cần thiết và chia tải theo route khi phù hợp.

## 6. Quy tắc SVG và icon viết bằng code

Thư mục đích là `frontend/src/assets/icons/`. Icon custom được viết thành component code render inline `<svg>` (ví dụ `SearchIcon.tsx`) và export qua `index.ts`; section gọi icon bằng import, không chép lại path SVG trong từng page.

**Trước khi thêm icon mới, bắt buộc kiểm tra theo thứ tự:**

1. Từ root repository, tìm file SVG: `rg --files -g "*.svg" .`; đồng thời tìm component icon hiện có trong source và `frontend/src/assets/icons/` nếu thư mục đó đã được tạo.
2. Tìm tên hoặc mục đích icon trong barrel `index.ts` và các component dùng chung.
3. Nếu icon đã có, import và dùng lại; không tạo thêm file hay bản sao mới.
4. Nếu chưa có, kiểm tra icon tương đương trong bộ icon Ant Design đang dùng; chỉ tạo SVG custom khi bộ hiện có không phù hợp.
5. SVG custom phải dùng `currentColor`, có kích thước/viewBox rõ ràng và xử lý truy cập: icon trang trí dùng `aria-hidden="true"`; icon mang ý nghĩa cần nhãn phù hợp.

Không tạo logo, ảnh cơ sở hoặc minh họa giả bằng SVG. Thương hiệu và ảnh thật chỉ thêm khi nhóm cung cấp/duyệt nguồn.

## 7. Responsive mobile-first

Viết style từ màn hình nhỏ lên; breakpoint cụ thể có thể điều chỉnh khi có code nhưng phải kiểm tra tối thiểu các viewport sau:

| Viewport | Mục tiêu kiểm tra |
|---|---|
| `375 × 812` | Mobile chính: không tràn ngang; CTA, form, menu và nội dung dùng được bằng chạm |
| `768 × 1024` | Tablet: cột và điều hướng chuyển trạng thái hợp lý |
| `1024 × 768` | Desktop nhỏ: Admin và bảng không che mất thao tác chính |
| `1440 × 900` | Desktop mục tiêu: bố cục có khoảng thở, không kéo dòng chữ quá dài |

Mobile: navigation Web thu gọn thành menu/drawer; Admin sidebar thành drawer hoặc nav thu gọn; form xếp dọc; nút thao tác có vùng chạm đủ lớn. Bảng Admin phải giữ các cột thiết yếu, cho phép cuộn ngang bên trong vùng bảng hoặc dùng layout hàng thay thế; không làm toàn trang tràn ngang. Desktop: dùng max-width cho nội dung, chia cột khi có lợi cho việc so sánh và giữ khoảng trắng. Kiểm tra thêm chiều rộng trung gian để phát hiện breakpoint gãy.

## 8. Trạng thái và tương tác

Mỗi nút, liên kết, item điều hướng, bộ lọc và thành phần có thể thao tác phải có trạng thái phù hợp:

| Trạng thái | Yêu cầu |
|---|---|
| `hover` | Có phản hồi nhẹ với thiết bị trỏ; không dùng hover làm cách duy nhất để thấy hành động |
| `active` | Nhấn xuống có phản hồi tức thì và không gây dịch chuyển layout |
| `focus-visible` | Viền/đánh dấu rõ khi dùng bàn phím, tương phản đủ với nền |
| `loading` | Nút/section có trạng thái chờ; chặn gửi lặp nhưng giữ dữ liệu form |
| `empty` | Nêu dữ liệu đang trống vì lý do gì và gợi ý thao tác tiếp theo |
| `error` | Thông báo lỗi cụ thể, đặt gần vùng bị ảnh hưởng, có hành động thử lại khi phù hợp |
| `disabled` | Nêu lý do không thể thao tác nếu lý do không hiển nhiên |
| `partial` | Với `GLOBAL`, hiển thị rõ site thiếu và dữ liệu chưa đầy đủ; không giả làm empty hoặc success toàn phần |

Animation chỉ dùng để giải thích kết quả thao tác: mở/đóng menu, accordion, drawer, xác nhận lưu hoặc trạng thái đang xử lý. Thời lượng chuyển trạng thái thường `120–180 ms`; tránh animation lặp tự động, parallax nặng và chuyển động làm người dùng chờ. Tôn trọng `prefers-reduced-motion`; trạng thái vẫn phải hiểu được khi tắt animation.

## 9. Tốc độ và ngân sách hiệu năng

Đo bằng millisecond khi phù hợp; đây là mục tiêu nghiệm thu, không phải cam kết trước khi có build và phép đo. Theo ngưỡng Core Web Vitals hiện được web.dev công bố, mục tiêu tại percentile 75, đo riêng mobile và desktop: **LCP ≤ 2500 ms**, **INP ≤ 200 ms**, **CLS ≤ 0.1** ([web.dev — Web Vitals](https://web.dev/articles/vitals)).

- Phản hồi trực quan cho thao tác bắt đầu ngay; trạng thái loading không đợi đến khi request kết thúc mới xuất hiện.
- Animation tương tác theo mục 8 dùng thời lượng tính bằng `ms`; không khóa luồng chính bằng animation dài.
- Ảnh dưới màn hình đầu được lazy-load; ảnh hero có kích thước/responsive source và không lazy-load nếu đó là nội dung LCP. Ưu tiên ảnh đã nén và định dạng phù hợp.
- Không nạp font, icon pack, component hoặc script không dùng. Tách tải theo route/page khi thư viện Admin không cần ở Web.
- Không dùng video nền, ảnh stock nặng, hiệu ứng blur lớn hoặc shadow dày làm trang chậm/khó đọc.
- Đánh giá bằng Lighthouse/DevTools sau khi có app chạy; ghi viewport, môi trường, số đo và điểm chưa đạt. Không tuyên bố “nhanh” nếu chưa đo.

## 10. Kiểm tra giao diện trước khi hoàn tất một page

Kiểm tra ngay khi làm từng page/section, không đợi hoàn tất toàn bộ sản phẩm:

1. Chạy lint, kiểm tra kiểu và build bằng script thực tế trong frontend; xử lý lỗi trước khi chuyển page tiếp theo.
2. Chạy ứng dụng và mở từng route; kiểm tra console, lỗi request, lỗi ảnh/SVG, trạng thái 404 và import sai.
3. Chụp và rà giao diện tại `375 × 812`, `768 × 1024`, `1024 × 768`, `1440 × 900`; xác nhận không tràn ngang, che nút, cắt chữ hoặc đè modal/drawer.
4. Kiểm tra bằng chuột, bàn phím và thao tác chạm: `hover`, `active`, `focus-visible`, loading, empty, lỗi, disabled và kết quả `GLOBAL` thiếu site.
5. Kiểm tra form sai/hợp lệ, gửi lặp, API lỗi và đổi kích thước trong khi drawer/modal đang mở.
6. Kiểm tra `prefers-reduced-motion`, độ tương phản, nhãn form, alt text và tên truy cập của icon/nút.
7. Đo hiệu năng theo mục 9 và ghi kết quả. Chỉ đánh dấu page hoàn tất khi có kết quả kiểm tra và ảnh chụp các viewport chính.

Không thay API bằng dữ liệu giả viết cứng trong giao diện hoàn thiện. Dữ liệu fixture chỉ dùng trong bài test cô lập, phải được phân biệt với dữ liệu ứng dụng thật.

## 11. Tiêu chí hoàn tất

- Component tuân thủ cây thư mục `web`/`admin`; section lớn có component và SCSS riêng; phần dùng chung được tái sử dụng đúng nơi.
- Nội dung Landing Page bám giọng văn thực tế; không dùng từ cấm, số liệu hoặc social proof chưa được xác minh.
- Palette không quá ba màu gốc; Ant Design được theme lại; SCSS Modules nhất quán, không có Tailwind class lặp dài và vô nghĩa.
- Icon được tìm trong assets/bộ icon trước khi thêm; nếu đã có thì import lại, không nhân bản.
- Page hoạt động ở mobile `375px` và desktop `1440px`, có kiểm tra tablet và kích thước trung gian.
- Tương tác có hover/active/focus/loading/empty/error khi phù hợp; animation ngắn và tôn trọng reduced-motion.
- Lint/typecheck/build và kiểm tra giao diện/performance có kết quả được ghi lại; không còn lỗi console, overflow hoặc lỗi hiển thị đã biết.
