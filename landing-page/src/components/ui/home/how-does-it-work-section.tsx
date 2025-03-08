"use client";

import { Element } from "react-scroll";
import React from 'react';
import { LogIn, Handshake, Gauge } from 'lucide-react';
import WhatsAppIcon from '@mui/icons-material/WhatsApp';
import StepCard from './cards';


const steps = [
    {
        step: 1,
        title: 'Crie sua conta',
        titleSize: "text-xl md:text-2xl",
        icon: <LogIn className="inline align-middle text-muted-foreground" size={25} />,
        description: (
            <>
                Faça login com sua conta <span className="font-bold">Facebook</span>, e conecte-se ao{' '}
                <span className="font-bold">Whatsapp Business</span>.<br />
                <br />Ou cadastre-se com e-mail e senha.
            </>
        ),
        descriptionMargin: "mt-10"
    },
    {
        step: 2,
        title: 'Apresente sua marca ao seu novo vendedor I.A.',
        titleSize: "text-md md:text-lg",
        icon: <Handshake className="inline align-middle text-muted-foreground" size={25} />,
        description: (
            <>

                <span className="font-bold">Compartilhe a essência do seu negócio</span>, descrevendo sua marca, missão e valores.{' '}
                <br /><br />Adicione também seu <span className="font-bold">catálogo de produtos e serviços</span> para um onboarding completo.
            </>
        ),
        descriptionMargin: "mt-6"
    },
    {
        step: 3,
        title: 'Dê o sinal verde – seu vendedor I.A está pronto',
        titleSize: "text-md md:text-lg",
        icon: <WhatsAppIcon className="inline align-middle text-muted-foreground w-8 h-8" />,
        description: (
            <>
                Seu novo funcionário I.A está pronto para assumir a <span className="font-bold">operação de vendas 24/7</span>.{' '}
                <br /><br />Habilite-o e <span className="font-bold">nunca mais deixe um lead sem resposta</span>.
            </>
        ),
        descriptionMargin: "mt-6"
    },
    {
        step: 4,
        title: 'Monitore. Otimize. Venda Mais.',
        titleSize: "text-md md:text-lg",
        icon: <Gauge className="inline align-middle text-muted-foreground" size={25} />,
        description: (
            <>
                No painel de controle, você pode <span className="font-bold">acompanhar conversões e vendas via WhatsApp</span>,{' '}
                bem como <span className="font-bold">analisar as conversas</span> entre os leads e seu vendedor I.A.

            </>
        ),
        descriptionMargin: "mt-6"
    },


];

export default function HowDoesItWorkSection() {
    return (
        <Element name="como-funciona" className="bg-background text-background-foreground ">
            <h2 className="text-3xl md:text-4xl text-center mt-12">Como Funciona</h2>
            <h3 className="text-lg md:text-xl text-center mt-2 mb-5 px-4">Transforme o <span className='font-bold'>WhatsApp no seu melhor canal de vendas</span> em apenas 4 passos, veja como é simples:</h3>
            {/* <div className="flex flex-col items-center sm:grid-cols-2 md:flex-row gap-8 p-8"> */}
            <div className="mx-auto">
            <div className="flex flex-col items-center justify-center place-items-center sm:grid sm:grid-cols-2 xl:flex xl:flex-row gap-8 p-8">
                {steps.map(({ step, title, titleSize, icon, description, descriptionMargin }, index) => (
                    <StepCard key={index} step={step} title={title} titleSize={titleSize} icon={icon} description={description} descriptionMargin={descriptionMargin} />
                ))}
            </div>
            </div>
        </Element>

    );
}