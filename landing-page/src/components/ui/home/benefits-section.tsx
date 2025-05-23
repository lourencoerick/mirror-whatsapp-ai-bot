"use client";

import { Element } from "react-scroll";
import { BetaSignupButton } from "@/components/ui/experiment-button";
import { AnimatedListDemo } from "@/components/ui/home/messages-poping-up";
import Image from "next/image";

const content = {
    firstArgument: {
        title: "Lambda Labs desenvolveu vendedores IA que não apenas respondem, mas persuadem.",
        description: "Fazendo uso de qualificação automática de leads, contorno de objeções e fechamento inteligente – enquanto você foca no crescimento.",
        buttonText: "Quero os melhores vendedores em minha operação",
        mobileButtonText: "Quero os melhores vendedores",
        videoSrc: "/jess.mp4",
        videoAlt: "Your browser does not support the video tag.",
    },
    secondArgument: {
        title: "Na dúvida, confie nos números – e venda com mais segurança.",
        description: `Na Lambda Labs, você tem à disposição um <span class="font-bold">painel de métricas completo</span> e a possibilidade de rodar testes constantemente. Isso significa entender, em tempo real, <span class="font-bold">o que gera resultados e o que precisa ser ajustado</span>.`,
        buttonText: "Quero descobrir o que funciona com meus leads",
        mobileButtonText: "Quero testar o que funciona",
        imageSrc: "/dashboard.png",
        imageAlt: "app.lambdalabs.com.br",
    },
    thirdArgument: {
        title: "Afogado em mensagens? Seu cliente não vai esperar!",
        description: `Clientes perguntam, negociam e querem resposta <span class="font-bold">na hora</span>. Enquanto você tenta responder um, <span class="font-bold">outros já foram embora</span>.`,
        listItems: [
            "Quanto mais mensagens acumulam, mais vendas você perde.",
            "Gerenciar a caixa de entrada se torna uma missão impossível.",
            "O WhatsApp não para, mas você precisa respirar.",
        ],
        buttonText: "Quero automatizar minhas vendas",
        mobileButtonText: "Quero automatizar minhas vendas",
    },
};

export default function BenefitsSection() {
    return (
        <Element name="beneficios" className="min-h-screen bg-secondary text-secondary-foreground flex flex-col items-center justify-center px-6">
            <h2 className="text-3xl lg:text-4xl text-center mt-8 mb-10 md:mb-20">Você pode continuar sobrecarregado... ou deixar a IA vender para você</h2>
            <div className="flex flex-col gap-20 md:gap-30 items-center">
                <div id="first-argument">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10 justify-center ">
                        <div>
                            <div className="flex flex-col md:mt-5 mb-5">
                                <h3 className="max-w-lg text-2xl lg:text-4xl text-start leading-relaxed">{content.firstArgument.title}</h3>
                                <p className="max-w-lg text-md lg:text-lg mt-2">{content.firstArgument.description}</p>
                            </div>
                            <BetaSignupButton className="hidden md:block max-w-lg text-md" aria-label="Inscrição Beta - Beneficio 1">{content.firstArgument.mobileButtonText}</BetaSignupButton>
                        </div>
                        <div className="max-w-lg flex flex-col justify-center items-center">
                            <video className="rounded-xl" preload="none" autoPlay muted loop controls={false} >
                                <source src={content.firstArgument.videoSrc} type="video/mp4" />
                                {content.firstArgument.videoAlt}
                            </video>
                            <BetaSignupButton className="block md:hidden w-full md:max-w-sm text-md mt-10" aria-label="Inscrição Beta - Beneficio 1">{content.firstArgument.mobileButtonText}</BetaSignupButton>
                        </div>
                    </div>
                </div>

                <div id="second-argument" className="">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10  items-center justify-center">
                        <div className="order-2 md:order-1  border-2">
                            <Image
                                alt={content.secondArgument.imageAlt}
                                className="w-full md:max-w-lg h-fit object-cover mx-auto"
                                src={content.secondArgument.imageSrc}
                                width={1000} 
                                height={500}
                            />                            
                        </div>
                        <div className="order-1 md:order-2">
                            <div className="flex flex-col mb-5 items-center">
                                <h3 className="max-w-lg text-2xl lg:text-4xl text-start leading-relaxed">{content.secondArgument.title}</h3>
                                <p className="max-w-lg text-md lg:text-lg mt-2" dangerouslySetInnerHTML={{ __html: content.secondArgument.description }}></p>
                            </div>
                            <BetaSignupButton className="hidden md:block max-w-lg text-md" aria-label="Inscrição Beta - Beneficio 2">{content.secondArgument.mobileButtonText}</BetaSignupButton>
                            
                        </div>
                        <div className="order-3"> 
                            <BetaSignupButton className="block md:hidden max-w-lg text-md mx-auto" aria-label="Inscrição Beta - Beneficio 2">{content.secondArgument.mobileButtonText}</BetaSignupButton>
                        </div>


                        
                        
                    </div>
                </div>

                <div id="third-argument" className="">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10 justify-center">
                        <div>
                            <div className="flex flex-col md:mt-5 mb-5">
                                <h3 className="max-w-lg text-2xl lg:text-4xl text-start leading-relaxed">{content.thirdArgument.title}</h3>
                                <p className="max-w-lg text-md lg:text-lg mt-2" dangerouslySetInnerHTML={{ __html: content.thirdArgument.description }}></p>
                                <ul className="list-disc pl-5 space-y-2">
                                    {content.thirdArgument.listItems.map((item, index) => (
                                        <li key={index}>{item}</li>
                                    ))}
                                </ul>
                            </div>
                            <BetaSignupButton className="hidden md:block max-w-lg text-md" aria-label="Inscrição Beta - Beneficio 3">{content.thirdArgument.buttonText}</BetaSignupButton>
                        </div>
                        <AnimatedListDemo />
                        
                        <BetaSignupButton className="block md:hidden max-w-lg text-md mx-auto mb-10 md:mb-0" aria-label="Inscrição Beta - Beneficio 3">{content.thirdArgument.mobileButtonText}</BetaSignupButton>

                    </div>
                </div>
            </div>
        </Element>
    );
}