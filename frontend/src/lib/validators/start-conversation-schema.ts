import { z } from 'zod'

export const startConversationSchema = z.object({
    phone_number: z
      .string()
      .min(10, "O número está muito curto")
      .max(15, "O número está muito longo")
      .regex(/^\d+$/, {
        message: "Formato inválido. Use apenas números, ex: 5511999999999",
      }),
  });