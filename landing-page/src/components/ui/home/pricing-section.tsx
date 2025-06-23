"use client";

import { EnterpriseCallout } from '@/components/ui/home/pricing/enterprise-callout';
import { PlanCard } from '@/components/ui/home/pricing/plan-card';
import { Plan } from '@/types/plan';
import React from 'react';
import { Element } from 'react-scroll';

// --- DATA UPDATE ---
// The plans array is now updated with beta-specific information.
// This data will activate the "beta mode" in the PlanCard component.
const plans: Plan[] = [
  {
    id: 'plan-basic',
    name: 'Essencial',
    basePrice: 'R$249',
    priceSuffix: '/mês',
    usagePriceText: '+ R$0,50 por mensagem IA excedente',
    description: 'Perfeito para autônomos e pequenos negócios que estão começando a automatizar.',
    features: [
      '1 número de WhatsApp',
      'Atendimento 24/7',
      'Contorno de objeções em tempo real',
      'Qualificação automática de leads',
      'Fechamento inteligente de vendas',
      'Follow-ups automáticos',  
      'Inclui 500 mensagens de IA',
      'Suporte por email',
    ],
    ctaText: 'Começar Agora', // Default text (for post-beta)
    betaOffer: { // This object activates beta mode
      priceText: 'Gratuito',
      offerDescription: 'Para empresas selecionadas'
    },
    betaCtaText: 'Quero Participar do Beta', // Specific CTA for beta
    stripePriceId: 'price_123abc_basic_hybrid',
  },
  {
    id: 'plan-pro',
    name: 'Pro',
    basePrice: 'R$499',
    priceSuffix: '/mês',
    usagePriceText: '+ R$0,50 por mensagem IA excedente',
    description: 'Ideal para negócios em crescimento que precisam de mais poder e integrações.',
    features: [
      'até 3 números de WhatsApp',
      'Atendimento 24/7',
      'Contorno de objeções em tempo real',
      'Qualificação automática de leads',
      'Fechamento inteligente de vendas',
      'Follow-ups automáticos',
      'Agendamento via Google Calendar',
      'Inclui 1.000 mensagens de IA',
      'Suporte prioritário por WhatsApp',      
    ],
    ctaText: 'Escolher Pro', // Default text (for post-beta)
    betaOffer: { // This object activates beta mode
      priceText: 'Gratuito',
      offerDescription: 'Para empresas selecionadas'
    },
    betaCtaText: 'Quero Participar do Beta', // Specific CTA for beta
    stripePriceId: 'price_123abc_pro_hybrid',
    isFeatured: true,
  },
];


const PricingSection = (): React.ReactElement => {
  return (
    <Element name="pricing" className="py-12 md:py-20 bg-background">
      <div className="container mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-normal text-foreground">
            Participe de nosso <span className='font-bold'>Beta Exclusivo</span>
          </h2>
          <p className="text-md md:text-lg text-foreground mt-4 max-w-2xl mx-auto">
            Seja um dos primeiros a transformar seu Whatsapp em uma máquina de vendas.<br/> Vagas limitadas para empresas selecionadas.
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto items-stretch">
          {plans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} />
          ))}
        </div>

        <div className="max-w-4xl mx-auto">
          <EnterpriseCallout />
        </div>

      </div>
    </Element>
  );
};

export default PricingSection;