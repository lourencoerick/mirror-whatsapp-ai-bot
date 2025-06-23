// components/landing/DogfoodingSection.tsx
"use client";

import { Button } from "@/components/ui/button"; // <--- 1. Importe o componente Button do Shadcn
import PhoneMockup from "@/components/ui/phone-mockup";
import Image from "next/image";
import Link from "next/link"; // <--- 2. Importe o Link do Next.js
import React from "react";
import { FaWhatsapp } from "react-icons/fa"; // <--- 3. Importe o ícone do WhatsApp
import { Element } from "react-scroll";

/**
 * A section that highlights our "dogfooding" philosophy.
 * It explains that we use our own AI to sell our product, serving as the ultimate proof of its value.
 * @returns {React.ReactElement} The rendered "dogfooding" section.
 */
const DogfoodingSection = (): React.ReactElement => {
  // 4. Reutilize a mesma lógica para construir o link do WhatsApp
  const whatsAppNumber = process.env.NEXT_PUBLIC_SALES_WHATSAPP_NUMBER || "5511941986775";
  // Mensagem específica para sabermos que o lead veio desta seção
  const preFilledMessage =
    "Olá! Vi a seção 'Veja em ação' e gostaria de saber mais sobre a plataforma.";

  const whatsAppLink = `https://wa.me/${whatsAppNumber}?text=${encodeURIComponent(
    preFilledMessage
  )}`;

  return (
    <Element
      name="proof"
      className="py-12 md:py-20 bg-secondary text-secondary-foreground"
    >
      <div className="container mx-auto px-6">
        <div className="text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            A Prova Definitiva: Compre de nosso Vendedor IA
          </h2>
          <p className="text-lg max-w-3xl mx-auto mb-12">
            Cansado de promessas? Nós também. Por isso, a IA que vai te atender
            agora é a mesma que fecha nossas vendas. Sem truques, sem
            vendedores. A prova está na conversa.
          </p>
        </div>

        <div className="flex flex-col md:flex-row items-center justify-center gap-12 max-w-6xl mx-auto">
          <div className="md:w-2/5">
            <PhoneMockup>
              <Image
                src="/static/images/whatsapp-chat-demo.png" // Lembre-se de ajustar o caminho se necessário
                alt="Demonstração da conversa com a IA de vendas no WhatsApp"
                width={270}
                height={550}
                className="object-cover w-full h-full"
              />
            </PhoneMockup>
          </div>
          <div className="md:w-3/5 text-left">
            <ul className="space-y-6">
              <li className="flex items-start">
                <span className="text-green-500 font-bold text-2xl mr-4 mt-1">
                  ✓
                </span>
                <div>
                  <h3 className="font-bold text-xl mb-1">Prova em Tempo Real</h3>
                  <p>
                    Você não vai agendar uma demo, você vai vivê-la. Sinta na
                    prática a experiência que seus clientes terão. Rápido,
                    inteligente e sem pressão.
                  </p>
                </div>
              </li>
              <li className="flex items-start">
                <span className="text-green-500 font-bold text-2xl mr-4 mt-1">
                  ✓
                </span>
                <div>
                  <h3 className="font-bold text-xl mb-1">
                    Comemos nossa própria ração
                  </h3>
                  <p>
                    Cada lead nosso é atendido pela mesma IA que estamos te
                    oferecendo. Ela qualifica, negocia e vende para nós todos os
                    dias. É o nosso teste de fogo diário.
                  </p>
                </div>
              </li>
              <li className="flex items-start">
                <span className="text-green-500 font-bold text-2xl mr-4 mt-1">
                  ✓
                </span>
                <div>
                  <h3 className="font-bold text-xl mb-1">
                    Transparência Radical
                  </h3>
                  <p>
                    A IA que vai te atender não é uma versão &quot;demo&quot;. É o produto
                    final. O que ela fizer por você, fará pelos seus clientes.
                    Simples assim.
                  </p>
                </div>
              </li>
            </ul>
          </div>
        </div>

        {/* ----- INÍCIO DA MUDANÇA: BOTÃO DE CTA ----- */}
        <div className="text-center mt-16">
          {whatsAppNumber && (
            <Button asChild size="lg" className="shadow-lg bg-green-500 text-slate-100 hover:hover:bg-green-600">
              <Link href={whatsAppLink} target="_blank" rel="noopener noreferrer">
                <FaWhatsapp className="mr-3 h-6 w-6" />
                Fale agora com nosso Vendedor IA
              </Link>
            </Button>
          )}
        </div>
        {/* ----- FIM DA MUDANÇA ----- */}
      </div>
    </Element>
  );
};

export default DogfoodingSection;