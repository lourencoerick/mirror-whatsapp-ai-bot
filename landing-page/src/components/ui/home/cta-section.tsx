"use client";

import { BetaSignupButton } from "@/components/ui/experiment-button";
import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";
import { Element } from "react-scroll";

interface CTASectionProps {
    bgColor?: string;
    hideLambda?: boolean
    title?: string
    description?: string
    buttonTitle?: string
}


export default function CTASection({ bgColor = "bg-background", hideLambda = false, title = "Escale suas vendas com IA e pare de perder clientes", description="Com Lambda Labs, você terá as melhores técnicas de vendas a sua disposição de forma rápida, simples e automática, 24/7", buttonTitle = "Quero contratar meu vendedor IA" }: CTASectionProps) {
    return (
        <Element name="cta" className={`${bgColor} min-h-fit text-foreground flex flex-col items-center justify-center py-6 px-6 gap-7`}>

            {!hideLambda && (<div className="relative w-30 aspect-[12/16] lambda-shape">
                <InteractiveGridPattern height={20} width={20} />
            </div>)}
            <div>
                <h2 className="text-3xl md:text-4xl text-center">{title}</h2>
                <p className="text-lg md:text-xl text-center">{description}</p>
            </div>

            <BetaSignupButton className="text-md md:text-xl px-2">{buttonTitle}</BetaSignupButton>

        </Element>
    );
}