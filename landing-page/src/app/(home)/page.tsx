"use client";

import { useEffect } from "react";
import {  scroller } from "react-scroll";

import HeroSection from "@/components/ui/home/hero-section";
import BenefitsSection from "@/components/ui/home/benefits-section";
import HowDoesItWorkSection from "@/components/ui/home/how-does-it-work-section";
import CTASection from "@/components/ui/home/cta-section";
import FaqSection from "@/components/ui/home/faq-section";

export default function HomePage() {
  useEffect(() => {
    if (window.location.hash) {
      const section = window.location.hash.replace("#", "");
      setTimeout(() => {
        scroller.scrollTo(section, {
          smooth: true,
          offset: -50,
          duration: 500,
        });
      }, 100);
    }
  }, []);
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
