# Quản lý Trung tâm Đào tạo Ngoại ngữ

## Giới thiệu dự án

Đây là đồ án thuộc môn **Cơ sở dữ liệu phân tán**, với đề tài **Quản lý trung tâm đào tạo ngoại ngữ**.

Dự án mô phỏng một trung tâm ngoại ngữ có nhiều cơ sở hoạt động tại các khu vực khác nhau. Mỗi cơ sở chịu trách nhiệm quản lý các thông tin phát sinh tại cơ sở của mình, đồng thời hệ thống vẫn có thể hỗ trợ việc tổng hợp và quản lý dữ liệu trên toàn bộ trung tâm.

Các cơ sở được sử dụng trong dự án gồm:

* Cơ sở Quận 1
* Cơ sở Quận 7
* Cơ sở Thủ Đức

## Mục tiêu dự án

Mục tiêu của dự án là xây dựng một hệ thống hỗ trợ quản lý hoạt động của trung tâm ngoại ngữ trong môi trường có nhiều cơ sở.

Thông qua đề tài này, nhóm hướng đến việc áp dụng kiến thức của môn **Cơ sở dữ liệu phân tán** vào một bài toán thực tế, trong đó dữ liệu được tổ chức và quản lý tại nhiều cơ sở khác nhau nhưng vẫn đảm bảo khả năng phối hợp và khai thác thông tin trên toàn hệ thống.

## Phạm vi quản lý

Hệ thống tập trung vào các nội dung chính sau:

* Quản lý học viên.
* Quản lý lớp học.
* Quản lý lịch học.
* Quản lý giáo viên.
* Quản lý khóa học và môn học.
* Quản lý đăng ký khóa học.
* Quản lý học phí.
* Quản lý điểm học viên.
* Quản lý thông tin theo từng cơ sở.

## Các nghiệp vụ chính

Dự án hỗ trợ các nghiệp vụ tiêu biểu của một trung tâm ngoại ngữ như:

* Đăng ký khóa học.
* Xếp lớp cho học viên.
* Chuyển học viên giữa các cơ sở.
* Đóng và quản lý học phí.
* Quản lý điểm học tập.
* Quản lý lịch học.
* Theo dõi hoạt động của từng cơ sở.
* Thống kê học viên theo cơ sở.

## Định hướng phân tán

Do trung tâm có nhiều cơ sở, dữ liệu trong hệ thống được định hướng phân tán theo từng chi nhánh.

Một số nhóm thông tin như:

* Học viên.
* Lớp học.
* Lịch học.
* Học phí.

có thể được quản lý tại cơ sở nơi dữ liệu phát sinh.

Ví dụ:

* Học viên đăng ký tại Quận 1 sẽ được quản lý tại cơ sở Quận 1.
* Lớp học được mở tại Quận 7 sẽ được quản lý tại cơ sở Quận 7.
* Lịch học của cơ sở Thủ Đức sẽ được quản lý tại cơ sở Thủ Đức.

Khi cần, hệ thống có thể tổng hợp thông tin từ nhiều cơ sở để phục vụ việc quản lý chung của toàn trung tâm.

## Mô hình hoạt động tổng quát

```text
                 TRUNG TÂM ĐÀO TẠO NGOẠI NGỮ
                           |
          ---------------------------------------
          |                  |                  |
   Cơ sở Quận 1       Cơ sở Quận 7      Cơ sở Thủ Đức
          |                  |                  |
     Học viên            Học viên           Học viên
     Lớp học             Lớp học            Lớp học
     Lịch học            Lịch học           Lịch học
     Học phí             Học phí            Học phí
```

Mỗi cơ sở có thể quản lý dữ liệu riêng, nhưng vẫn thuộc cùng một hệ thống quản lý chung.

## Ý nghĩa của đề tài

Đề tài **Quản lý trung tâm đào tạo ngoại ngữ** có nghiệp vụ gần gũi, dễ hình dung và phù hợp để áp dụng các kiến thức của môn **Cơ sở dữ liệu phân tán**.

Thông qua dự án, nhóm có thể nghiên cứu cách tổ chức dữ liệu tại nhiều cơ sở, xử lý các nghiệp vụ liên quan đến nhiều chi nhánh và thực hiện các chức năng quản lý trên toàn hệ thống.

## Thông tin môn học

* **Môn học:** Cơ sở dữ liệu phân tán
* **Đề tài:** Đề tài 10 - Quản lý trung tâm đào tạo ngoại ngữ
* **Số lượng cơ sở:** 2–3 cơ sở
* **Cơ sở minh họa:** Quận 1, Quận 7, Thủ Đức
