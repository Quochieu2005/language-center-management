import type { Metadata } from "next";
import PublicCatalogPage from "@/components/web/catalog/PublicCatalogPage";

export const metadata: Metadata = { title: "Khóa học | [Tên trung tâm]", description: "Khám phá danh mục khóa học ngoại ngữ." };

export default function CoursesPage() {
  return <PublicCatalogPage kind="courses" />;
}
