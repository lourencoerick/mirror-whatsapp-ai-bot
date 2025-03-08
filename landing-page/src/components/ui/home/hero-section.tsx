"use client";

import { Element } from "react-scroll";
import { Button } from "@/components/ui/button";
import { TypingAnimation } from "@/components/magicui/typing-animation";
import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";
import { Link as ScrollLink } from "react-scroll";
import { BetaSignupButton } from "@/components/ui/experiment-button";
import WhatsAppIcon from '@mui/icons-material/WhatsApp';


export default function HeroSection() {

  return (
    <Element name="hero" className="pt-20 pb-10 bg-background text-foreground">
      <div className="container mx-auto px-4 flex flex-col md:flex-row items-center">
        <div className="w-full md:w-7/10 text-center md:text-left">
          <TypingAnimation
            className="text-3xl sm:text-4xl lg:text-7xl font-normal mb-4 typing-container"
            as="h1"
            style={{ whiteSpace: "pre-line" }}
          >
            {`I.A. que vende.\nDados que decidem.\nResultados que escalam`}
          </TypingAnimation>
          <p className="text-lg sm:text-xl lg:text-3xl mb-8">
            <span className="font-bold">
              Seu negócio vendendo mais, sem contratar mais.
            </span><br />
            Nossos <span className="font-bold">vendedores I.A.</span> automatizam suas conversas no <span className="whitespace-nowrap">WhatsApp <WhatsAppIcon /></span> para que você{" "}
            <span className="font-bold">aumente suas conversões e foque no crescimento de seu negócio.</span>
          </p>
          <div className="flex flex-col md:flex-row justify-center md:justify-start gap-4">
            <BetaSignupButton>Começar Agora</BetaSignupButton>

            <ScrollLink
              activeClass="active"
              to="beneficios"
              spy={true}
              smooth={true}
              offset={-50} // ajuste se tiver header fixo
              duration={500}
              className="cursor-pointer"

            >
              <Button variant="outline" size="lg">
                Saber Mais
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
