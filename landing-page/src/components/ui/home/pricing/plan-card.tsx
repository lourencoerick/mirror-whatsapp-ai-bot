"use client";

import { Check, Loader2 } from 'lucide-react';
import React, { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Plan } from '@/types/plan';

interface PlanCardProps {
  plan: Plan;
}

/**
 * Displays a pricing plan card that adapts its appearance and behavior
 * for standard subscriptions or special beta offers.
 */
export function PlanCard({ plan }: PlanCardProps): React.ReactElement {
  const [isLoading, setIsLoading] = useState(false);

  /**
   * Handles the call-to-action, redirecting to beta sign-up page
   * or to a standard checkout flow.
   */
  const handleCtaClick = () => {
    setIsLoading(true);

    if (plan.betaOffer) {
      // --- BETA SIGN-UP LOGIC (UPDATED) ---
      toast.info("Redirecionando para inscrição...", {
        description: "Você está um passo mais perto de automatizar suas vendas!",
      });
      
      const appUrl = process.env.NEXT_PUBLIC_APP_URL;
      if (!appUrl) {
          console.error("A variável de ambiente NEXT_PUBLIC_APP_URL não está definida.");
          toast.error("Erro de configuração", { description: "Não foi possível encontrar a URL de inscrição." });
          setIsLoading(false);
          return;
      }

      // We use `plan.id` as the offer_id for the sign-up URL.
      const signUpUrl = `${appUrl}/sign-up?offer_id=${plan.id}`;
      console.log(`Redirecting to beta sign-up URL: ${signUpUrl}`);

      // The timeout gives the user a moment to read the toast message.
      setTimeout(() => {
        window.location.href = signUpUrl;
        // No need to reset isLoading, as the page will navigate away.
      }, 1500);

    } else {
      // --- STANDARD CHECKOUT LOGIC ---
      console.log(`Initiating checkout for plan: "${plan.name}" with Stripe Price ID: ${plan.stripePriceId}`);
      toast.success("Redirecionando para o pagamento...", {
        description: `Você selecionou o plano ${plan.name}.`,
      });
      // Your Stripe checkout logic would go here.
      setTimeout(() => setIsLoading(false), 2000);
    }
  };

  const ctaButtonText = plan.betaOffer ? plan.betaCtaText : plan.ctaText;

  return (
    <Card
      className={`relative flex flex-col h-full shadow-md hover:shadow-lg transition-shadow duration-300 ${
        plan.isFeatured ? 'border-2 border-green-600 ring-4 ring-green-600/20' : 'border'
      }`}
    >
      {plan.betaOffer && (
        <div className="absolute top-0 right-0 bg-green-600 text-white text-xs font-bold px-3 py-1 rounded-tr-lg rounded-bl-lg z-10">
          BETA
        </div>
      )}
      <CardHeader>
        <CardTitle className="text-2xl font-semibold">{plan.name}</CardTitle>
        <CardDescription className="h-12 text-gray-800 dark:text-gray-300">{plan.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex-grow">
        <div className="mb-6">
          {plan.betaOffer ? (
            <div>
              <p className="text-2xl font-semibold line-through text-gray-400">
                {plan.basePrice}{plan.priceSuffix}
              </p>
              <p className="text-4xl font-extrabold text-green-700 dark:text-green-500 mt-1">{plan.betaOffer.priceText}</p>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">{plan.betaOffer.offerDescription}</p>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">(Não é necessário cartão de crédito)</p>
            </div>
          ) : (
            <div>
              <span className="text-5xl font-extrabold text-foreground">{plan.basePrice}</span>
              <span className="text-xl font-medium text-gray-500">{plan.priceSuffix}</span>
              <p className="mt-1 text-sm font-medium text-green-700">{plan.usagePriceText}</p>
            </div>
          )}
        </div>
        <ul className="space-y-3 text-gray-700">
          {plan.features.map((feature, index) => (
            <li key={index} className="flex items-start text-gray-600 dark:text-gray-400">
              <Check className="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </CardContent>
      <CardFooter>
        <Button
          onClick={handleCtaClick}
          disabled={isLoading}
          size="lg"
          className="w-full font-semibold"
          variant={plan.isFeatured ? 'default' : 'outline'}
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Processando...
            </>
          ) : (
            ctaButtonText
          )}
        </Button>
      </CardFooter>
    </Card>
  );
}