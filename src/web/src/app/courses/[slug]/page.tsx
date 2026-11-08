import type { Metadata } from "next";
import PublicCatalogPage from "@/components/web/catalog/PublicCatalogPage";

type CourseDetailProps = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: CourseDetailProps): Promise<Metadata> {
  const { slug } = await params;
  return { title: `${slug} | Khóa học`, description: "Thông tin chi tiết khóa học ngoại ngữ." };
}

export default async function CourseDetailPage({ params }: CourseDetailProps) {
  const { slug } = await params;
  return <PublicCatalogPage kind="course-detail" slug={slug} />;
}
