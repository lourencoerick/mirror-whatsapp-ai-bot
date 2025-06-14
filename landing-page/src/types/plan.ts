/**
 * @file Defines the data structure for a pricing plan.
 */

/**
 * Describes the special offer for a beta plan.
 * @property {string} priceText - The text to display as the price (e.g., "Gratuito").
 * @property {string} offerDescription - A short description of the offer (e.g., "Para empresas selecionadas").
 */
interface BetaOffer {
  priceText: string;
  offerDescription: string;
}

/**
 * Represents a single pricing plan available for subscription.
 * Supports standard and beta phase pricing models.
 *
 * @property {string} id - A unique identifier for the plan.
 * @property {string} name - The public name of the plan (e.g., "Pro").
 * @property {string} basePrice - The standard fixed price (e.g., "R$249"). Used for display even in beta.
 * @property {string} priceSuffix - The frequency of the base price (e.g., "/mês").
 * @property {string} usagePriceText - A text explaining variable costs (e.g., "+ R$0,50 por mensagem").
 * @property {string} description - A short sentence describing the ideal user for this plan.
 * @property {string[]} features - A list of features included in the plan.
 * @property {string} ctaText - The standard call-to-action text (e.g., "Assinar Agora").
 * @property {BetaOffer} [betaOffer] - If present, the card will render in "beta mode" with this information.
 * @property {string} [betaCtaText] - The CTA text specifically for the beta offer (e.g., "Quero Participar").
 * @property {boolean} [isFeatured=false] - If true, the plan will be visually highlighted.
 * @property {string} [stripePriceId] - The ID of the price in Stripe for post-beta checkout.
 */
export interface Plan {
  id: string;
  name: string;
  basePrice: string;
  priceSuffix: string;
  usagePriceText: string;
  description:string;
  features: string[];
  ctaText: string;
  betaOffer?: BetaOffer;
  betaCtaText?: string;
  isFeatured?: boolean;
  stripePriceId?: string;
}