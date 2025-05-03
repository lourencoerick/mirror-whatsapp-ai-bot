import * as z from "zod";

// Schema Zod correspondente ao CompanyProfileSchema (ajuste conforme necessário)
// Tornamos a maioria dos campos opcionais aqui, pois o PUT pode ser parcial,
// mas podemos adicionar refinamentos (.min(1)) onde necessário para a UI.

export const offeringValidationSchema = z.object({
  // Adicionar ID opcional se useFieldArray o gerar e precisarmos dele
  // id: z.string().optional(), // Depende se useFieldArray adiciona um ID
  name: z.string().min(1, "Offering name is required").max(255),
  short_description: z
    .string()
    .min(1, "Short description is required")
    .max(500),
  key_features: z.array(z.string()).optional().default([]),
  bonus_items: z.array(z.string()).optional().default([]),
  price_info: z.string().max(255).nullable().optional(),
  link: z
    .string()
    .url({ message: "Please enter a valid URL." })
    .or(z.literal(""))
    .nullable()
    .optional(),
});

export const companyProfileValidationSchema = z.object({
  // id: z.string().uuid().optional(), // Geralmente não editável no form
  company_name: z
    .string()
    .min(1, { message: "Company name is required." })
    .max(255),
  website: z
    .string()
    .url({ message: "Please enter a valid URL." })
    .or(z.literal(""))
    .nullable()
    .optional(), // Permite URL, string vazia, null ou undefined
  address: z.string().max(500).nullable().optional(),
  business_description: z
    .string()
    .min(1, { message: "Business description is required." })
    .max(5000), // Max length maior
  target_audience: z.string().max(500).nullable().optional(),
  sales_tone: z
    .string()
    .min(1, { message: "Sales tone is required." })
    .max(255),
  language: z.string().min(1, { message: "Language is required." }).max(10), // Ex: 'pt-BR'
  communication_guidelines: z.array(z.string()).optional(),
  ai_objective: z
    .string()
    .min(1, { message: "AI objective is required." })
    .max(1000),
  key_selling_points: z.array(z.string()).optional(),
  offering_overview: z.array(offeringValidationSchema).optional().default([]), // Usa o schema aninhado

  delivery_options: z.array(z.string()).optional(),
  opening_hours: z.string().max(255).nullable().optional(),
  fallback_contact_info: z.string().max(500).nullable().optional(),
  // profile_version: z.number().int().optional(), // Geralmente não editável
});

// Tipo TypeScript inferido a partir do schema Zod
export type CompanyProfileFormData = z.infer<
  typeof companyProfileValidationSchema
>;

export type OfferingFormData = z.infer<typeof offeringValidationSchema>;
