// src/lib/validators/beta-request-schema.ts
import { z } from "zod";

export const betaRequestSchema = z.object({
  contact_name: z.string().min(2, {
    message:
      "O nome de contato é obrigatório e deve ter pelo menos 2 caracteres.",
  }),
  company_name: z
    .string()
    .min(2, { message: "O nome da empresa é obrigatório." })
    .optional()
    .or(z.literal("")), // Opcional, mas se preenchido, min 2
  company_website: z
    .string()
    .url({ message: "Por favor, insira uma URL válida para o site." })
    .optional()
    .or(z.literal("")),
  business_description: z.string().min(10, {
    message: "Descreva brevemente seu negócio (mínimo 10 caracteres).",
  }),
  beta_goal: z.string().min(10, {
    message:
      "Descreva seu principal objetivo com o beta (mínimo 10 caracteres).",
  }),
  has_sales_team: z.boolean().optional(), // Ou z.enum(['true', 'false']) se vier de um radio string
  sales_team_size: z.string().optional(),
  avg_leads_per_period: z.string().optional(),
  current_whatsapp_usage: z.string().optional(),
  willing_to_give_feedback: z
    .boolean({
      required_error:
        "Por favor, confirme se está disposto a fornecer feedback.",
    })
    .refine((value) => value === true, {
      message: "Você deve concordar em fornecer feedback para participar.", // Mensagem se não for true
    }),

  agree_to_terms: z
    .boolean({
      required_error:
        "Você deve concordar com os Termos de Uso do Programa Beta.",
    })
    .refine((value) => value === true, {
      // Garante que o checkbox foi marcado
      message:
        "Você deve concordar com os Termos de Uso do Programa Beta para continuar.",
    }),
});

export type BetaRequestFormValues = z.infer<typeof betaRequestSchema>;
