import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";

const faqItems = [
    {
        value: "item-1",
        question: "Preciso saber programar para usar o Vendedor I.A.?",
        answer: "Não! Nosso Vendedor I.A. é fácil de configurar e funciona sem código. Em poucos minutos, ele já pode começar a atender seus clientes no WhatsApp."
    },
    {
        value: "item-2",
        question: "O Vendedor I.A. realmente pode aumentar minhas vendas?",
        answer: "Sim! Ele responde seus clientes imediatamente, mantém conversas engajadas e nunca deixa uma mensagem sem resposta – aumentando suas chances de conversão."
    },
    {
        value: "item-3",
        question: "Como o Vendedor I.A. aprende sobre minha empresa?",
        answer: "Você compartilha com ele informações sobre sua marca, valores e produtos. Assim, ele entende como representar seu negócio da melhor forma e oferecer um atendimento mais personalizado."
    },
    {
        value: "item-4",
        question: "Posso conectar o Vendedor I.A. ao meu WhatsApp Business?",
        answer: "Sim! Basta fazer login com o Facebook e conectar sua conta do WhatsApp Business. O processo é rápido e seguro."
    },
    {
        value: "item-5",
        question: "O que acontece se eu não gostar do Vendedor I.A.?",
        answer: "Sem problemas! Você pode testar gratuitamente e cancelar a qualquer momento, sem compromisso."
    },
    {
        value: "item-6",
        question: "O Vendedor I.A. atende apenas pelo WhatsApp?",
        answer: "Sim, no momento ele é especializado em atendimento via WhatsApp, garantindo a melhor experiência para você e seus clientes."
    },
    {
        value: "item-7",
        question: "Quanto tempo leva para configurar o Vendedor I.A.?",
        answer: "Em menos de 15 minutos ele já estará pronto para atender seus clientes."
    },
    {
        value: "item-8",
        question: "Posso integrar com um CRM?",
        answer: "Sim! Nossa plataforma permite integração com diversos CRMs para que você gerencie melhor seus leads e automatize ainda mais seu processo de vendas."
    },
];


export default function FaqSection() {
    return (
        <section className="bg-secondary text-secondary-foreground  items-center justify-center px-10 md:px-60 py-10">
            <h1 className="text-3xl md:text-4xl mb-6 text-center">Perguntas Frequentes</h1>
            <Accordion type="single" collapsible className="space-y-4">
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
        </section>
    );
}
