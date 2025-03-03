import Card from "./feature-card";
import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";

export default function BenefitsSection() {

    return (
        <section className="min-h-screen bg-secondary text-secondary-foreground flex flex-col items-center px-6">
            <h1 className="text-2xl md:text-4xl text-center my-10">Você pode continuar sobrecarregado... ou deixar a I.A. vender para você</h1>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-10  justify-center">
                <div>
                    <div className="flex flex-col  md:mt-5 mb-5">
                        <h2 className="max-w-lg text-2xl md:text-4xl text-start leading-relaxed">Lambda Labs desenvolve vendedores I.A. que não apenas respondem, mas persuadem.</h2>
                        <p className="max-w-lg text-md md:text-lg mt-2">Fazendo uso de qualificação automática de leads, contorno de objeções e fechamento inteligente – enquanto você foca no crescimento.</p>
                        
                        

                    </div>
                    <InteractiveHoverButton className="max-w-sm">Quero automatizar minhas vendas</InteractiveHoverButton>
                </div>

                



                <div className="border-2 max-w-lg">
                    <video className="rounded-xl" preload="none" autoPlay muted loop>
                        <source src="/jess.mp4" type="video/mp4" />
                        Your browser does not support the video tag.
                    </video>
                </div>
            </div>




            {/* Grid de cards */}
            {/* <div className="grid gap-8 grid-cols-1 md:grid-cols-3 mt-10">
                <Card
                    icon={<span className="text-4xl">🚀</span>}
                    title="Rendimiento Rápido"
                    description="Experimenta velocidades impresionantes con nuestra solución optimizada."
                />
                <Card
                    icon={<span className="text-4xl">🔒</span>}
                    title="Seguridad Robusta"
                    description="Tus datos están protegidos con medidas de seguridad de última generación."
                />
                <Card
                    icon={<span className="text-4xl">💡</span>}
                    title="Soluciones Innovadoras"
                    description="Aprovecha la tecnología de vanguardia para impulsar la creatividad."
                />
            </div> */}
        </section>
    );
}