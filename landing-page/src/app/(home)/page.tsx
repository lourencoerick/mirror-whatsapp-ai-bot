
import HeroSection from "@/components/ui/home/hero-section";
import BenefitsSection from "@/components/ui/home/benefits-section";
import HowDoesItWorkSection from "@/components/ui/home/how-does-it-work-section";
import CTASection from "@/components/ui/home/cta-section";
import FaqSection from "@/components/ui/home/faq-section";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col">
      <HeroSection />
      <BenefitsSection />
      <HowDoesItWorkSection />
      <CTASection />
      <FaqSection />
    </main>
  )
}
