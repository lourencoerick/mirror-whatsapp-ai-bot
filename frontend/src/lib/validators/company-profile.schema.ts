import * as z from "zod";

import { components } from "@/types/api";
type AvailabilityRule = components["schemas"]["AvailabilityRuleSchema"];

export const getDefaultAvailabilityRules = (): AvailabilityRule[] => {
  const days = [0, 1, 2, 3, 4, 5, 6]; // 0=Domingo, ..., 6=Sábado
  return days.map((day) => ({
    dayOfWeek: day,
    isEnabled: [1, 2, 3, 4, 5].includes(day), // Padrão: Seg-Sex ativo
    startTime: "09:00",
    endTime: "18:00",
  }));
};

// Schema Zod correspondente ao CompanyProfileSchema (ajuste conforme necessário)
// Tornamos a maioria dos campos opcionais aqui, pois o PUT pode ser parcial,
// mas podemos adicionar refinamentos (.min(1)) onde necessário para a UI.

export const availabilityRuleValidationSchema = z
  .object({
    dayOfWeek: z.number().min(0).max(6),
    isEnabled: z.boolean(),
    startTime: z.string().regex(/^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/),
    endTime: z.string().regex(/^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/),
  })
  .refine(
    (data) => {
      // Se o dia estiver habilitado, o horário de fim deve ser maior que o de início.
      if (data.isEnabled) {
        return data.endTime > data.startTime;
      }
      // Se estiver desabilitado, a validação passa.
      return true;
    },
    {
      message: "O horário de fim deve ser posterior ao de início.",
      path: ["endTime"], // Associa o erro ao campo de horário de fim.
    }
  );

export const availabilityRulesArraySchema = z
  .array(availabilityRuleValidationSchema)
  .length(7, "Você precisa definir regras para todos os 7 dias da semana");

export const offeringValidationSchema = z
  .object({
    // Adicionar ID opcional se useFieldArray o gerar e precisarmos dele
    id: z.string().optional(), // Depende se useFieldArray adiciona um ID
    name: z.string().min(1, "Offering name is required").max(255),
    short_description: z
      .string()
      .min(1, "Short description is required")
      .max(500),
    key_features: z.array(z.string()).optional().default([]),
    bonus_items: z.array(z.string()).optional().default([]),
    price: z
      .number({
        invalid_type_error: "Price must be a number.",
      })
      .nonnegative({ message: "Price must be zero or a positive number." })
      .nullable()
      .optional(),
    price_info: z.string().max(255).nullable().optional(),
    link: z
      .string()
      .url({ message: "Please enter a valid URL." })
      .or(z.literal(""))
      .nullable()
      .optional(),
    requires_scheduling: z.boolean().default(false),
    duration_minutes: z.number().positive().optional().nullable(),
  })
  .refine(
    (data) => {
      if (
        data.requires_scheduling &&
        (data.duration_minutes === null ||
          data.duration_minutes === undefined ||
          data.duration_minutes < 15)
      ) {
        return false;
      }
      return true;
    },
    {
      message:
        "A duração é obrigatória quando o agendamento é necessário. E deve ser maior ou igual a 15 min.",
      path: ["duration_minutes"],
    }
  );

export const companyProfileValidationSchema = z
  .object({
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
    accepted_payment_methods: z.array(z.string()).optional(),
    is_scheduling_enabled: z.boolean().default(false),
    scheduling_calendar_id: z.string().optional().nullable(),
    scheduling_min_notice_hours: z
      .number()
      .positive("Deve ser um número positivo.")
      .min(0.25, "A antecedência mínima é de 15 minutos (0.25 horas)."),
    availability_rules: availabilityRulesArraySchema.optional().nullable(),

    offering_overview: z.array(offeringValidationSchema).optional().default([]), // Usa o schema aninhado

    delivery_options: z.array(z.string()).optional(),
    opening_hours: z.string().max(255).nullable().optional(),
    fallback_contact_info: z.string().max(500).nullable().optional(),
    // profile_version: z.number().int().optional(), // Geralmente não editável
  })
  .refine(
    (data) => {
      // Se o agendamento NÃO estiver habilitado, a validação passa.
      if (!data.is_scheduling_enabled) {
        return true;
      }
      // Se o agendamento ESTIVER habilitado, então o ID do calendário deve existir.
      // Usamos `!!` para converter um valor "truthy" (como uma string não vazia) para `true`.
      return !!data.scheduling_calendar_id;
    },
    {
      // Mensagem de erro que será mostrada se a condição acima falhar.
      message:
        "Você precisa selecionar um calendário quando o agendamento está habilitado.",
      // Associa este erro especificamente ao campo do seletor de calendário.
      path: ["scheduling_calendar_id"],
    }
  )
  .refine(
    (data) => {
      // Segunda regra de refinamento para as regras de disponibilidade.
      if (!data.is_scheduling_enabled) {
        return true;
      }
      // Se o agendamento ESTIVER habilitado, então as regras de disponibilidade devem existir.
      return (
        data.availability_rules != null && data.availability_rules.length === 7
      );
    },
    {
      message:
        "Você precisa configurar os horários de disponibilidade quando o agendamento está habilitado.",
      // Associa este erro ao campo de regras de disponibilidade.
      path: ["availability_rules"],
    }
  );

// Tipo TypeScript inferido a partir do schema Zod
export type CompanyProfileFormData = z.infer<
  typeof companyProfileValidationSchema
>;

export type OfferingFormData = z.infer<typeof offeringValidationSchema>;
