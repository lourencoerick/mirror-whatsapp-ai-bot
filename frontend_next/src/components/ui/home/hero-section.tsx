"use client";

import { Button } from "@/components/ui/button";
import { TypingAnimation } from "@/components/magicui/typing-animation";
import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";
import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";

export default function HeroSection() {

  return (
    <section className="py-20 bg-background text-foreground">
      <div className="container mx-auto px-4 flex flex-col md:flex-row items-center">
        <div className="w-full md:w-7/10 text-center md:text-left">
          <TypingAnimation
            className="text-4xl md:text-7xl font-normal mb-4 typing-container"
            as="h1"
            style={{ whiteSpace: "pre-line" }}
          >
            {`I.A. que vende.\nDados que decidem.\nResultados que escalam.`}
          </TypingAnimation>
          <p className="text-xl md:text-3xl mb-8">
            <span className="font-bold">
              Seu negócio vendendo mais, sem contratar mais.
            </span><br />
            Nossos <span className="font-bold">vendedores I.A.</span> cuidam das conversas enquanto{" "}
            <span className="font-bold">você foca no crescimento.</span>
          </p>
          <div className="flex flex-col md:flex-row justify-center md:justify-start gap-4">
            <InteractiveHoverButton>Começar Agora</InteractiveHoverButton>
            <Button variant="outline" size="lg">
              Saber Mais
            </Button>
          </div>
        </div>

        <div className="w-full md:w-3/10 mt-8 md:mt-0 flex justify-center relative hidden md:block">
          <div className="relative z-10 w-full aspect-[12/16] lambda-shape">
              <InteractiveGridPattern />
          </div>
        </div>
      </div>
    </section>
  );
}
