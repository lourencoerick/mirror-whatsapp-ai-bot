import { z } from "zod";

const phoneRegex = /^\+?[1-9]\d{1,14}$/; // Exemplo: +5511987654321 ou 5511987654321 ou 11987654321

export const AddContactSchema = z.object({
  name: z.string().min(1, { message: "O nome não pode ficar em branco." }).max(100, { message: "O nome é muito longo."}).optional().or(z.literal('')), // Nome opcional, mas não pode ser só espaços se fornecido
  phone_number: z.string()
    .min(10, { message: "Número de telefone inválido." }) // Mínimo razoável
    .regex(phoneRegex, { message: "Formato de telefone inválido." }), // Valida o formato
  email:  z.preprocess(
    (val) => {
      if (typeof val === "string" && val.trim() === "") {
        return undefined;
      }
      return val;
    },
    z
      .string()
      .email({ message: "Formato de email inválido." })
      .max(100, { message: "O email é muito longo." })
      .optional()
  ),
});

export type AddContactFormData = z.infer<typeof AddContactSchema>;