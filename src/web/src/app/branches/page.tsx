import type { Metadata } from "next";
import PublicCatalogPage from "@/components/web/catalog/PublicCatalogPage";
import { BRAND_NAME } from "@/lib/brand";

export const metadata: Metadata = { title: `Cơ sở | ${BRAND_NAME}`, description: "Thông tin các cơ sở đào tạo." };

export default function BranchesPage() {
  return <PublicCatalogPage kind="branches" />;
}
