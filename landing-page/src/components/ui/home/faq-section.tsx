"use client";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Element } from "react-scroll";

const faqItems = [
    {
        value: "item-1",
        question: "Preciso saber programar para usar o Vendedor IA?",
        answer: "Não! Nosso Vendedor IA é fácil de configurar e funciona sem código. Em poucos minutos, ele já pode começar a atender seus clientes no WhatsApp."
    },
    {
        value: "item-2",
        question: "O Vendedor IA realmente pode aumentar minhas vendas?",
        answer: "Sim! Ele responde seus clientes imediatamente, mantém conversas engajadas e nunca deixa uma mensagem sem resposta – aumentando suas chances de conversão."
    },
    {
        value: "item-3",
        question: "Como o Vendedor IA aprende sobre minha empresa?",
        answer: "Você compartilha com ele informações sobre sua marca, valores e produtos. Assim, ele entende como representar seu negócio da melhor forma e oferecer um atendimento mais personalizado."
    },
    {
        value: "item-4",
        question: "Posso conectar o Vendedor IA ao meu WhatsApp Business?",
        answer: "Sim! Basta fazer login e conectar sua conta do WhatsApp Business com o Facebook Business ou via QR Code. O processo é rápido e seguro."
    },
    {
        value: "item-5",
        question: "O que acontece se eu não gostar do Vendedor IA?",
        answer: "Sem problemas! Você pode testar gratuitamente e cancelar a qualquer momento, sem compromisso."
    },
    {
        value: "item-6",
        question: "O Vendedor IA atende apenas pelo WhatsApp?",
        answer: "Sim, no momento ele é especializado em atendimento via WhatsApp, garantindo a melhor experiência para você e seus clientes."
    },
    {
        value: "item-7",
        question: "Quanto tempo leva para configurar o Vendedor IA?",
        answer: "Em menos de 5 minutos ele já estará pronto para atender seus clientes."
    },

];


export default function FaqSection() {
    return (
        <Element name="faq" className="bg-secondary text-secondary-foreground  items-center justify-center px-10 py-10 ">
            <h2 className="text-3xl md:text-4xl mb-6 text-center">Perguntas Frequentes</h2>
            <Accordion type="single" collapsible className="space-y-4 max-w-4xl mx-auto">
                {faqItems.map(item => (
                    <AccordionItem key={item.value} value={item.value}>
                        <AccordionTrigger className="text-lg md:text-xl">
                            {item.question}
                        </AccordionTrigger>
                        <AccordionContent className="text-md md:text-lg">
                            {item.answer}
                        </AccordionContent>
                    </AccordionItem>
                ))}
            </Accordion>
        </Element>
    );
}
