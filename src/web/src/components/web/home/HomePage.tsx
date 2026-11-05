import WebFooter from "@/components/web/layout/WebFooter";
import WebHeader from "@/components/web/layout/WebHeader";
import BenefitsSection from "./sections/BenefitsSection/BenefitsSection";
import PublicCourseCatalog from "@/components/web/catalog/PublicCourseCatalog";
import FAQSection from "./sections/FAQSection/FAQSection";
import FinalCTASection from "./sections/FinalCTASection/FinalCTASection";
import HeroSection from "./sections/HeroSection/HeroSection";
import ProgramSection from "./sections/ProgramSection/ProgramSection";
import BlogPreviewSection from "./sections/BlogPreviewSection/BlogPreviewSection";
import ContactSection from "./sections/ContactSection/ContactSection";
import styles from "./HomePage.module.scss";

export default function HomePage() {
  return (
    <div className={styles.page}>
      <WebHeader />
      <main id="main-content">
        <HeroSection />
        <BenefitsSection />
        <ProgramSection />
        <PublicCourseCatalog preview />
        <BlogPreviewSection />
        <FAQSection />
        <ContactSection />
        <FinalCTASection />
      </main>
      <WebFooter />
    </div>
  );
}
