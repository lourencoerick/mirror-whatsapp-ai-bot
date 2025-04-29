/* eslint-disable @typescript-eslint/no-unused-vars */
import { zodResolver } from "@hookform/resolvers/zod";
import React, { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

import { Input, inputVariants } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { cn } from "@/lib/utils";
import {
  AddContactSchema,
  type AddContactFormData,
} from "@/lib/validators/contact.schema";
import type { Contact } from "@/types/contact"; // Importar tipo Contact
import { InputMask } from "@react-input/mask";
import { Loader2 } from "lucide-react";

/**
 * Props for the EditContactForm component.
 */
interface EditContactFormProps {
  /** The contact data to pre-fill the form. */
  contact: Contact;
  /** Callback function executed on successful contact update. */
  onSuccess: () => void;
  /** Optional: Callback to close the dialog/modal containing the form. */
  onCancel?: () => void;
}

/**
 * Form component for editing an existing contact.
 * Handles validation, pre-population, and API submission (PUT).
 *
 * @component
 * @param {EditContactFormProps} props - Component props.
 * @returns {React.ReactElement} The rendered form.
 */
export const EditContactForm: React.FC<EditContactFormProps> = ({
  contact,
  onSuccess,
  onCancel,
}) => {
  const authenticatedFetch = useAuthenticatedFetch();
  const [apiError, setApiError] = useState<string | null>(null);

  // Formatting phone to Brazilian format with +55
  // TODO: search a more generic format
  const maskPhone = (v: string) => {
    const unmaskPhone = (v: string) => v.replace(/\D/g, ""); // "+55 (11) 98765-4321" → "5511987654321"
    const digits = unmaskPhone(v).slice(-11); // 11 digits
    if (digits.length < 10) return digits;

    const [, dd, first, last] = digits.match(/(\d{2})(\d{5})(\d{4})/)!;
    return `+55 (${dd}) ${first}-${last}`; // "+55 (11) 98765-4321"
  };

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset, // Use reset to update default values if contact changes
  } = useForm<AddContactFormData>({
    resolver: zodResolver(AddContactSchema),
    // Preencher o formulário com os dados do contato existente
    defaultValues: {
      name: contact.name || "",
      phone_number: maskPhone(contact.phone_number ?? ""),
      email: contact.email || undefined,
    },
  });

  // Efeito para resetar o formulário se o contato prop mudar (caso o modal seja reutilizado)
  useEffect(() => {
    reset({
      name: contact.name || "",
      phone_number: maskPhone(contact.phone_number ?? ""),
      email: contact.email || "",
    });
  }, [contact, reset]);

  /**
   * Handles form submission for editing. Sends data via PUT request.
   * @param {AddContactFormData} data - Validated form data.
   */
  const onSubmit = async (data: AddContactFormData) => {
    setApiError(null);
    try {
      const response = await authenticatedFetch(
        `/api/v1/contacts/${contact.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      );

      if (!response.ok) {
        let errorDetail = "Falha ao atualizar contato.";
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (jsonError) {
          /* Ignore */
        }
        throw new Error(errorDetail);
      }

      toast.success("Contato atualizado com sucesso!");
      onSuccess();
    } catch (error: unknown) {
      console.error("Error updating contact:", error);
      let errorMessage = "Ocorreu um erro inesperado.";
      if (error instanceof Error && error.message) {
        errorMessage = error.message;
      }
      setApiError(errorMessage); // Mantém o erro no formulário se necessário
      toast.error(errorMessage);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {apiError && (
        <p className="text-sm text-red-600 bg-red-100 p-2 rounded border border-red-300">
          {apiError}
        </p>
      )}

      {/* Fields are the same as AddContactForm */}
      <div className="space-y-1">
        <Label htmlFor="edit-name">Nome</Label>
        <Input
          id="edit-name"
          {...register("name")}
          placeholder="Nome (opcional)"
          disabled={isSubmitting}
        />
        {errors.name && (
          <p className="text-xs text-red-500">{errors.name.message}</p>
        )}
      </div>
      <div className="space-y-1">
        <Label htmlFor="edit-phone_number">Telefone</Label>
        <InputMask
          id="edit-phone_number"
          mask="+55 (__) _____-____"
          placeholder="+55 (11) 98765-4321"
          replacement={{ _: /\d/ }}
          autoFocus
          {...register("phone_number", {
            setValueAs: (value: string) => value.replace(/\D/g, ""), // Removes all non-digits
          })}
          className={cn(inputVariants)}
          disabled={isSubmitting}
          required
        />
        {errors.phone_number && (
          <p className="text-xs text-red-500">{errors.phone_number.message}</p>
        )}
      </div>
      <div className="space-y-1">
        <Label htmlFor="edit-email">Email</Label>
        <Input
          id="edit-email"
          type="email"
          {...register("email")}
          placeholder="email@exemplo.com (opcional)"
          disabled={isSubmitting}
        />
        {errors.email && (
          <p className="text-xs text-red-500">{errors.email.message}</p>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex justify-end gap-2 pt-2">
        {onCancel && (
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancelar
          </Button>
        )}
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Atualizando...
            </>
          ) : (
            "Salvar Alterações"
          )}
        </Button>
      </div>
    </form>
  );
};
