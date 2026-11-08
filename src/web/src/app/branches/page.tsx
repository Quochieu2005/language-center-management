import type { Metadata } from "next";
import PublicCatalogPage from "@/components/web/catalog/PublicCatalogPage";

export const metadata: Metadata = { title: "Cơ sở | [Tên trung tâm]", description: "Thông tin các cơ sở đào tạo." };

export default function BranchesPage() {
  return <PublicCatalogPage kind="branches" />;
}
