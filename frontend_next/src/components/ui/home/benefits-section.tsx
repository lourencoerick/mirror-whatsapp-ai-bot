import Card from "./feature-card";
import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";
import { AnimatedListDemo } from "@/components/ui/home/messages-poping-up";
import { Safari } from "@/components/magicui/safari";

export default function BenefitsSection() {

    return (
        <section className="min-h-screen bg-secondary text-secondary-foreground flex flex-col items-center px-6">
            <h1 className="text-2xl md:text-4xl text-center mt-8 mb-10 md:mb-20 ">Você pode continuar sobrecarregado... ou deixar a I.A. vender para você</h1>
            <div className="flex flex-col gap-30">
                <div id="first-argument">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10  justify-center">
                        <div>
                            <div className="flex flex-col  md:mt-5 mb-5">
                                <h2 className="max-w-lg text-2xl md:text-4xl text-start leading-relaxed">Lambda Labs desenvolveu vendedores I.A. que não apenas respondem, mas persuadem.</h2>
                                <p className="max-w-lg text-md md:text-lg mt-2">Fazendo uso de qualificação automática de leads, contorno de objeções e fechamento inteligente – enquanto você foca no crescimento.</p>



                            </div>
                            <InteractiveHoverButton className="hidden md:block max-w-lg text-md">Quero os melhores vendedores em minha operação</InteractiveHoverButton>
                        </div>

                        <div className="max-w-lg flex flex-col justify-center items-center">
                            <video className="rounded-xl" preload="none" autoPlay muted loop>
                                <source src="/jess.mp4" type="video/mp4" />
                                Your browser does not support the video tag.
                            </video>
                            <InteractiveHoverButton className="block md:hidden max-w-sm text-xl mt-10">Quero automatizar minhas vendas</InteractiveHoverButton>
                        </div>

                    </div>
                </div>


                <div id="second-argument" className="">


                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10  justify-center">
                        <div className="relative">

                            <Safari
                                url="app.lambdalabs.com.br"
                                className="max-w-lg h-fit object-cover"// aspect-video"-mt-45 
                                imageSrc="/dashboard.png"
                            />
                        </div>
                        <div>
                            <div className="flex flex-col mb-5">
                                <h2 className="max-w-lg text-2xl md:text-4xl text-start leading-relaxed">Na dúvida, confie nos números – e venda com mais segurança.</h2>
                                <p className="max-w-lg text-md md:text-lg mt-2">Na Lambda Labs, você tem à disposição um <span className="font-bold">painel de métricas completo</span> e a possibilidade de rodar testes constantemente. Isso significa entender, em tempo real, <span className="font-bold">o que gera resultados e o que precisa ser ajustado</span>.</p>
                            </div>
                            <InteractiveHoverButton className="hidden md:block max-w-lg text-md">Quero descobrir o que funciona com meus leads</InteractiveHoverButton>
                        </div>

                    </div>
                </div>

                <div id="third-argument" className="">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10  justify-center">
                        <div>
                            <div className="flex flex-col  md:mt-5 mb-5">
                                <h2 className="max-w-lg text-2xl md:text-4xl text-start leading-relaxed">Afogado em mensagens? Seu cliente não vai esperar!</h2>
                                <p className="max-w-lg text-md md:text-lg mt-2">Clientes perguntam, negociam e querem resposta <span className="font-bold">na agora</span>. Enquanto você tenta responder um, <span className="font-bold">outros já foram embora</span>.</p>
                                <ul className="list-disc pl-5 space-y-2">
                                    <li>Quanto mais mensagens acumulam, mais vendas você perde.</li>
                                    <li>Gerenciar a caixa de entrada se torna uma missão impossível.</li>
                                    <li>O WhatsApp não para, mas você precisa respirar.</li>
                                </ul>



                            </div>
                            <InteractiveHoverButton className="hidden md:block max-w-sm text-xl">Quero automatizar minhas vendas</InteractiveHoverButton>
                        </div>


                        <AnimatedListDemo></AnimatedListDemo>

                    </div>

                </div>


            </div>
        </section>
    );
}