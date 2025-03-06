import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";
import { AnimatedListDemo } from "@/components/ui/home/messages-poping-up";
import { Safari } from "@/components/magicui/safari";

const content = {
    firstArgument: {
        title: "Lambda Labs desenvolveu vendedores I.A. que não apenas respondem, mas persuadem.",
        description: "Fazendo uso de qualificação automática de leads, contorno de objeções e fechamento inteligente – enquanto você foca no crescimento.",
        buttonText: "Quero os melhores vendedores em minha operação",
        videoSrc: "/jess.mp4",
        videoAlt: "Your browser does not support the video tag.",
    },
    secondArgument: {
        title: "Na dúvida, confie nos números – e venda com mais segurança.",
        description: `Na Lambda Labs, você tem à disposição um <span class="font-bold">painel de métricas completo</span> e a possibilidade de rodar testes constantemente. Isso significa entender, em tempo real, <span class="font-bold">o que gera resultados e o que precisa ser ajustado</span>.`,
        buttonText: "Quero descobrir o que funciona com meus leads",
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
    },
};

export default function BenefitsSection() {
    return (
        <section className="min-h-screen bg-secondary text-secondary-foreground flex flex-col items-center px-6">
            <h1 className="text-3xl md:text-4xl text-center mt-8 mb-10 md:mb-20">Você pode continuar sobrecarregado... ou deixar a I.A. vender para você</h1>
            <div className="flex flex-col gap-30">
                <div id="first-argument">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10 justify-center">
                        <div>
                            <div className="flex flex-col md:mt-5 mb-5">
                                <h2 className="max-w-lg text-2xl md:text-4xl text-start leading-relaxed">{content.firstArgument.title}</h2>
                                <p className="max-w-lg text-md md:text-lg mt-2">{content.firstArgument.description}</p>
                            </div>
                            <InteractiveHoverButton className="hidden md:block max-w-lg text-md">{content.firstArgument.buttonText}</InteractiveHoverButton>
                        </div>
                        <div className="max-w-lg flex flex-col justify-center items-center">
                            <video className="rounded-xl" preload="none" autoPlay muted loop>
                                <source src={content.firstArgument.videoSrc} type="video/mp4" />
                                {content.firstArgument.videoAlt}
                            </video>
                            <InteractiveHoverButton className="block md:hidden max-w-sm text-xl mt-10">{content.firstArgument.buttonText}</InteractiveHoverButton>
                        </div>
                    </div>
                </div>

                <div id="second-argument" className="">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10 justify-center">
                        <div className="order-2 md:order-1 relative">
                            <Safari
                                url={content.secondArgument.imageAlt}
                                className="max-w-md md:max-w-lg h-fit object-cover"
                                imageSrc={content.secondArgument.imageSrc}
                            />
                        </div>
                        <div className="order-1 md:order-2">
                            <div className="flex flex-col mb-5">
                                <h2 className="max-w-lg text-2xl md:text-4xl text-start leading-relaxed">{content.secondArgument.title}</h2>
                                <p className="max-w-lg text-md md:text-lg mt-2" dangerouslySetInnerHTML={{ __html: content.secondArgument.description }}></p>
                            </div>
                            <InteractiveHoverButton className="hidden md:block max-w-lg text-md">{content.secondArgument.buttonText}</InteractiveHoverButton>
                        </div>
                    </div>
                </div>

                <div id="third-argument" className="">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-10 justify-center">
                        <div>
                            <div className="flex flex-col md:mt-5 mb-5">
                                <h2 className="max-w-lg text-2xl md:text-4xl text-start leading-relaxed">{content.thirdArgument.title}</h2>
                                <p className="max-w-lg text-md md:text-lg mt-2" dangerouslySetInnerHTML={{ __html: content.thirdArgument.description }}></p>
                                <ul className="list-disc pl-5 space-y-2">
                                    {content.thirdArgument.listItems.map((item, index) => (
                                        <li key={index}>{item}</li>
                                    ))}
                                </ul>
                            </div>
                            <InteractiveHoverButton className="hidden md:block max-w-lg text-md">{content.thirdArgument.buttonText}</InteractiveHoverButton>
                        </div>
                        <AnimatedListDemo />
                    </div>
                </div>
            </div>
        </section>
    );
}