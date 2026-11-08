import type { Metadata } from "next";
import { ArticlePage } from "@/components/web/catalog/PublicInfoPage";
import { articles } from "@/lib/content/articles";

type Props = { params: Promise<{ slug: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const article = articles.find((item) => item.slug === slug);
  return { title: article ? `${article.title} | Blog` : "Bài viết | Blog", description: article?.excerpt ?? "Bài viết tham khảo về học ngoại ngữ." };
}
export default async function Page({ params }: Props) { const { slug } = await params; return <ArticlePage slug={slug} />; }
