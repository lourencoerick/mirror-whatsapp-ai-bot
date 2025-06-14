'use client';

import WhatsAppIcon from '@mui/icons-material/WhatsApp';

import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";
import { TypingAnimation } from "@/components/magicui/typing-animation";
import { BetaSignupButton } from '@/components/ui/beta/beta-signup-button'; // 2. Importing the new simple button
import DemoVideoSection from '@/components/ui/home/demo-video-section'; // 1. Re-using our standard video section
import Navbar from "@/components/ui/home/navbar";

/**
 * A simplified, high-conversion landing page for beta sign-ups.
 * It features a hero promise, video proof, and a single, clear call-to-action button.
 */
export default function BetaSignupPage() {
  return (
    <main className="bg-background text-foreground">
      <Navbar hideSignupButton={true} />

      {/* Hero Section */}
      <section className="container mx-auto px-4 flex flex-col md:flex-row items-center mt-10">
        <div className="w-full md:w-7/10 text-center md:text-left">
          <TypingAnimation
            duration={60}
            className="text-4xl md:text-5xl font-normal mt-0 mb-4 typing-container"
            as="h1"
            style={{ whiteSpace: "pre-line" }}
          >
            Seja um dos primeiros a transformar seu WhatsApp em uma máquina de vendas
          </TypingAnimation>
          <p className="text-xl md:text-2xl mb-8 leading-relaxed">
            Lambda Labs está <span className="font-bold">oferecendo acesso antecipado</span> para empresas selecionadas.<br />
            Inscreva-se para concorrer à <span className="font-bold">oportunidade de testar gratuitamente</span> nossa Inteligência Artificial que <span className="font-bold">automatiza suas vendas pelo </span>WhatsApp <WhatsAppIcon />.
          </p>
        </div>
        <div className="w-full md:w-3/10 mt-8 md:mt-0 justify-center relative hidden md:flex">
          <div className="relative z-10 w-full aspect-[12/16] lambda-shape">
            <InteractiveGridPattern />
          </div>
        </div>
      </section>
      
      {/* Video Proof Section */}
      <DemoVideoSection />

      {/* Final Call-to-Action Section */}
      <section className="container mx-auto px-4 py-16 text-center">
        <h2 className="text-3xl font-bold mb-4">Pronto para começar?</h2>
        <p className="text-lg text-gray-600 dark:text-gray-400 mb-8">
          Clique abaixo para ir à página de cadastro e garantir seu acesso antecipado.
        </p>
        {/* 3. Replaced the entire form with our simple button */}
        <BetaSignupButton />
      </section>
    </main>
  );
}