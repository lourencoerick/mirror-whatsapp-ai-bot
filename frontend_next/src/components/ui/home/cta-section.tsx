import { BetaSignupButton } from "@/components/ui/experiment-button";
import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";

export default function CTASection() {
    return (
        <section className="bg-background text-foreground flex flex-col items-center justify-center px-6">

                <div className="relative w-30 aspect-[12/16] lambda-shape mt-10">
                    <BetaSignupButton height={20} width={20}/>
                </div>

            <h1 className="text-3xl md:text-4xl text-center">Escale suas vendas com I.A. e pare de perder clientes</h1>
            <p className="text-lg md:text-xl text-center">Com Lambda Labs, você terá as melhores técnicas de vendas a sua disposição de forma rápida, simples e automática, 24/7</p>
            <BetaSignupButton className="text-lg md:text-xl mt-15 mb-10">Quero contratar meu vendedor I.A.</BetaSignupButton>

        </section>
    );
}