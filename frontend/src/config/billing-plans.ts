// src/config/billing-plans.ts

interface PlanDisplayDetails {
  name: string;
  tier: string;
}
export const PLAN_DETAILS_MAP: Record<string, PlanDisplayDetails> = {
  prod_SMPv4MdWl6hBBC: { name: "Plano Básico", tier: "basic" },
  prod_SN3qNHRMF7W8FR: { name: "Plano Pro", tier: "pro" },
  prod_SN3rpbkaXAWgpA: {
    name: "Plano Enterprise",
    tier: "enterprise",
  },
};
