import WebPageLayout from "@/components/web/layout/WebPageLayout";
import HeroSection from "./sections/HeroSection/HeroSection";
import CoursePreviewSection from "./sections/CoursePreviewSection/CoursePreviewSection";
import BlogSection from "./sections/BlogSection/BlogSection";
import FAQSection from "./sections/FAQSection/FAQSection";
import FinalCTASection from "./sections/FinalCTASection/FinalCTASection";

export default function HomePage() {
  return (
    <WebPageLayout>
      <HeroSection />
      <CoursePreviewSection />
      <BlogSection />
      <FAQSection />
      <FinalCTASection />
    </WebPageLayout>
  );
}
