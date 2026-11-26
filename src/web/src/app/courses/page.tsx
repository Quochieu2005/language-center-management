import type { Metadata } from "next";
import PublicCatalogPage from "@/components/web/catalog/PublicCatalogPage";
import { BRAND_NAME } from "@/lib/brand";

export const metadata: Metadata = { title: `Khóa học | ${BRAND_NAME}`, description: "Khám phá danh mục khóa học ngoại ngữ." };

export default function CoursesPage() {
  return <PublicCatalogPage kind="courses" />;
}
