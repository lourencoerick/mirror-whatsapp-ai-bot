// src/app/dashboard/support/page.tsx (ou src/app/support/page.tsx)
"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useLayoutContext } from "@/contexts/layout-context"; // Ajuste o caminho
import { LifeBuoy, Mail, MessageSquare } from "lucide-react";
import { useEffect } from "react";

const supportEmail = "tecnologia@lambdalabs.com.br";
const betaFeedbackEmail = "tecnologia@lambdalabs.com.br";

const faqData = [
  {
    question: "Como funciona o período beta?",
    answer:
      "Durante o período beta, você terá acesso gratuito às funcionalidades designadas do plano beta. Esperamos seu feedback para nos ajudar a melhorar a plataforma. O acesso pode ser revogado ou modificado conforme nossos Termos de Uso do Programa Beta.",
  },
  {
    question: "Como reporto um bug ou dou feedback?",
    answer: `A melhor forma de reportar bugs ou dar feedback é através do nosso email de suporte beta: ${betaFeedbackEmail}.`,
  },
  {
    question: "Como funciona o faturamento das mensagens de IA?",
    answer:
      "Além da assinatura base do plano, o uso de mensagens geradas pela IA também será gratuito, porém haverá um limite. Cada mensagem de IA enviada pela plataforma conta como uma unidade. Você pode acompanhar seu uso na seção 'Métricas'.",
  },
  {
    question: "Posso cancelar minha assinatura a qualquer momento?",
    answer:
      "Sim, você pode gerenciar sua assinatura, incluindo o cancelamento, através do portal do cliente Stripe, acessível na sua página de 'Faturamento' dentro do dashboard.",
  },
  // Adicione mais perguntas e respostas
];

export default function SupportPage() {
  const { setPageTitle } = useLayoutContext();

  useEffect(() => {
    setPageTitle?.("Suporte e Ajuda");
  }, [setPageTitle]);

  return (
    <div className="container mx-auto max-w-3xl px-4 py-12">
      <div className="text-center mb-12">
        <LifeBuoy className="mx-auto h-16 w-16 text-blue-600 mb-4" />
        <h1 className="text-4xl font-extrabold tracking-tight text-gray-900 sm:text-5xl">
          Central de Ajuda Lambda Labs
        </h1>
        <p className="mt-4 max-w-2xl mx-auto text-xl text-gray-600">
          Precisa de ajuda ou tem alguma dúvida? Estamos aqui para você.
        </p>
      </div>

      <div className="space-y-8">
        {/* Seção de Contato */}
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Entre em Contato</CardTitle>
            <CardDescription>
              Nossa equipe está pronta para te ajudar com qualquer questão.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start space-x-3">
              <Mail className="h-6 w-6 text-blue-500 mt-1 flex-shrink-0" />
              <div>
                <h3 className="font-semibold">Suporte Geral por Email</h3>
                <p className="text-sm text-muted-foreground">
                  Para dúvidas gerais, problemas técnicos ou assistência.
                </p>
                <a
                  href={`mailto:${supportEmail}`}
                  className="text-blue-600 hover:underline font-medium"
                >
                  {supportEmail}
                </a>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <MessageSquare className="h-6 w-6 text-green-500 mt-1 flex-shrink-0" />
              <div>
                <h3 className="font-semibold">Feedback do Programa Beta</h3>
                <p className="text-sm text-muted-foreground">
                  Encontrou um bug? Tem sugestões para o beta? Nos conte!
                </p>
                <a
                  href={`mailto:${betaFeedbackEmail}`}
                  className="text-green-600 hover:underline font-medium"
                >
                  {betaFeedbackEmail}
                </a>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Seção de FAQ */}
        {faqData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-2xl">
                Perguntas Frequentes (FAQ)
              </CardTitle>
              <CardDescription>
                Encontre respostas rápidas para as dúvidas mais comuns.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="single" collapsible className="w-full">
                {faqData.map((faqItem, index) => (
                  <AccordionItem value={`item-${index}`} key={index}>
                    <AccordionTrigger className="text-left hover:no-underline">
                      {faqItem.question}
                    </AccordionTrigger>
                    <AccordionContent className="text-muted-foreground pt-1 pb-3">
                      {faqItem.answer}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
        )}
      </div>

      <p className="mt-12 text-center text-sm text-gray-500">
        Não encontrou o que precisava? Não hesite em nos contatar diretamente.
      </p>
    </div>
  );
}
