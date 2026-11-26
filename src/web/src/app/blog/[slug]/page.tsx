import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";
import { ApiError } from "@/lib/api/client";
import { blogApi, type PublicBlogArticleSummary } from "@/lib/api/blog";
import { ArticlePage } from "@/components/web/catalog/PublicInfoPage";
import { articles } from "@/lib/content/articles";

type Props = { params: Promise<{ slug: string }> };
const getPublicArticle = cache((slug: string) => blogApi.publicArticle(slug));

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const { result } = await getPublicArticle(slug);
    return { title: `${result.title} | Blog`, description: result.excerpt };
  } catch {
    const article = articles.find((item) => item.slug === slug);
    return { title: article ? `${article.title} | Blog` : "Bài viết | Blog", description: article?.excerpt ?? "Bài viết tham khảo về học ngoại ngữ." };
  }
}

export default async function Page({ params }: Props) {
  const { slug } = await params;
  let article = null;
  try {
    const { result } = await getPublicArticle(slug);
    article = result;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
  }
  let latest: PublicBlogArticleSummary[] = [];
  try {
    latest = (await blogApi.publicArticles()).results.filter((item) => item.slug !== slug).slice(0, 4);
  } catch {
    // shortcut: the sidebar is optional; the article itself is what matters.
  }
  return <ArticlePage article={article} latest={latest} />;
}
