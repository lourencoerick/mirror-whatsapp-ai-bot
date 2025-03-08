"use client";

import { BetaSignupButton } from "@/components/ui/experiment-button";
import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";
import { Element } from "react-scroll";


export default function CTASection() {
    return (
        <Element name="cta" className="bg-background text-foreground flex flex-col items-center justify-center px-6">

                <div className="relative w-30 aspect-[12/16] lambda-shape mt-10">
                    <InteractiveGridPattern height={20} width={20}/>
                </div>

            <h2 className="text-3xl md:text-4xl text-center">Escale suas vendas com I.A. e pare de perder clientes</h2>
            <p className="text-lg md:text-xl text-center">Com Lambda Labs, você terá as melhores técnicas de vendas a sua disposição de forma rápida, simples e automática, 24/7</p>
            <BetaSignupButton className="text-md md:text-xl mt-15 mb-10 px-2">Quero contratar meu vendedor I.A.</BetaSignupButton>

        </Element>
    );
}