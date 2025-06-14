"use client";

import WhatsAppIcon from '@mui/icons-material/WhatsApp';
import { PlayCircle } from "lucide-react"; // 1. Import the icon
import { Element, Link as ScrollLink } from "react-scroll";

import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";
import { TypingAnimation } from "@/components/magicui/typing-animation";
import { Button } from "@/components/ui/button";
import { BetaSignupButton } from "@/components/ui/experiment-button";

/**
 * The hero section for the main landing page.
 * It contains the main headline, a short description, and primary calls-to-action.
 */
export default function HeroSection() {
  return (
    <Element name="hero" className="pt-20 pb-10 bg-background text-foreground">
      <div className="container mx-auto px-4 flex flex-col md:flex-row items-center">
        <div className="w-full md:w-7/10 text-center md:text-left">
          <TypingAnimation
            className="text-3xl sm:text-4xl lg:text-7xl font-normal mb-4 typing-container"
            as="h1"
            // The pre-line style is important to respect the `\n` for line breaks.
            style={{ whiteSpace: "pre-line" }}
          >
            {`IA que vende.\nDados que decidem.\nResultados que escalam`}
          </TypingAnimation>
          <p className="text-lg sm:text-xl lg:text-3xl mb-8">
            <span className="font-bold">
              Seu negócio vendendo mais, sem contratar mais.
            </span><br />
            Nossos <span className="font-bold">vendedores IA</span> automatizam suas conversas no <span className="whitespace-nowrap">WhatsApp <WhatsAppIcon /></span> para que você{" "}
            <span className="font-bold">aumente suas conversões e foque no crescimento de seu negócio.</span>
          </p>
          <div className="flex flex-col md:flex-row justify-center md:justify-start gap-4">
            <BetaSignupButton aria-label="Inscrição Beta - Hero Section">Começar Agora</BetaSignupButton>

            {/* 2. Update the scroll link to point to the "demo" section */}
            <ScrollLink
              href="#demo"
              activeClass="active"
              to="demo"
              spy={true}
              smooth={true}
              offset={-50}
              duration={500}
              className="cursor-pointer"
            >
              {/* 3. Change button text and add the icon */}
              <Button variant="outline" size="lg" className="cursor-pointer w-full">
                <PlayCircle className="mr-2 h-5 w-5" />
                Ver Demonstração
              </Button>
            </ScrollLink>
          </div>
        </div>

        <div className="w-full md:w-3/10 mt-8 md:mt-0 flex justify-center relative hidden md:block">
          <div className="relative z-10 w-full aspect-[12/16] lambda-shape">
            <InteractiveGridPattern height={25} width={25} />
          </div>
        </div>
      </div>
    </Element>
  );
}