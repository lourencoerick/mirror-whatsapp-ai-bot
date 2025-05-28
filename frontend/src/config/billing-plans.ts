// src/config/billing-plans.ts
import { Plan } from "@/components/ui/billing/plan-card";

export const plansData: Plan[] = [
  {
    id: "beta",
    tier: "pro",
    name: "Plano Beta VIP",
    price: "Grátis", // Ou "Trial Longo"
    currency: "BRL",
    stripeProductId: "prod_SLYFjJMKBp22Xz",
    stripePriceId: "price_1RTAIqQJjxj1kzOyGTlA2iFd", // << SEU PRICE ID DO PLANO BETA
    features: [
      "Acesso a todos os recursos",
      "Suporte VIP para Beta Testers",
      "Influencie o futuro da plataforma",
    ],
    description:
      "Exclusivo para nossos parceiros beta. Ajude-nos a refinar a ferramenta!",
    isBeta: true,
    buttonText: "Ativar Acesso Beta Gratuito", // Texto mais específico
    highlight: true,
  },
];

export const getBetaPlan = (): Plan | undefined => {
  return plansData.find((plan) => plan.isBeta);
};

export const getPlanDetailsByStripeIds = (
  priceId?: string,
  productId?: string | null
): Plan | undefined => {
  if (!priceId && !productId) {
    return undefined;
  }

  // Tenta encontrar pelo Price ID primeiro, pois é mais específico
  if (priceId) {
    const planByPrice = plansData.find((p) => p.stripePriceId === priceId);
    if (planByPrice) {
      return planByPrice;
    }
  }

  // Se não encontrou por Price ID (ou se não foi fornecido), tenta por Product ID
  if (productId) {
    const planByProduct = plansData.find(
      (p) => p.stripeProductId === productId
    );
    if (planByProduct) {
      return planByProduct;
    }
  }

  return undefined; // Nenhum plano encontrado
};
