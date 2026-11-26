import { blogApi } from "@/lib/api/blog";
import { articles } from "@/lib/content/articles";

export type ArticleCard = { slug: string; category: string; readingTime: string; title: string; excerpt: string; cover: string | null };

/** Published articles for public pages; falls back to the bundled sample posts only when the API is unreachable. */
export async function loadArticleCards(): Promise<ArticleCard[]> {
  try {
    const { results } = await blogApi.publicArticles();
    return results.map((item) => ({
      slug: item.slug, category: item.category.name.toUpperCase(), readingTime: `${item.reading_time_minutes} phút đọc`,
      title: item.title, excerpt: item.excerpt, cover: item.cover_url ?? null,
    }));
  } catch {
    return articles.map((item) => ({ ...item, cover: null }));
  }
}
