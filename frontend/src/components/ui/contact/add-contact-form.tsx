import React, { useState } from 'react'; 
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from "sonner"; 

import { Button } from '@/components/ui/button';
import { Input, inputVariants } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AddContactSchema, type AddContactFormData } from '@/lib/validators/contact.schema';
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch';
import { Loader2 } from 'lucide-react';
import { InputMask } from '@react-input/mask';
import { cn } from "@/lib/utils"

/**
 * Props for the AddContactForm component.
 */
interface AddContactFormProps {
  /** Callback function executed on successful contact creation. */
  onSuccess: () => void;
  /** Optional: Callback to close the dialog/modal containing the form. */
  onCancel?: () => void;
}

/**
 * Form component for adding a new contact.
 * Handles validation using Zod and react-hook-form, and API submission.
 * Uses toast notifications for feedback.
 *
 * @component
 * @param {AddContactFormProps} props - Component props.
 * @returns {React.ReactElement} The rendered form.
 */
export const AddContactForm: React.FC<AddContactFormProps> = ({ onSuccess, onCancel }) => {
  const authenticatedFetch = useAuthenticatedFetch();
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<AddContactFormData>({
    resolver: zodResolver(AddContactSchema),
    defaultValues: { name: '', phone_number: '', email: undefined }, 
  });

  /**
   * Handles form submission. Sends data to the backend API.
   * @param {AddContactFormData} data - Validated form data.
   */
  const onSubmit = async (data: AddContactFormData) => {
    setApiError(null);
    try {
      const response = await authenticatedFetch('/api/v1/contacts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        let errorDetail = "Falha ao adicionar contato.";
        try {
            const errorData = await response.json();
            errorDetail = errorData.detail || errorDetail;
        } catch (jsonError) { /* Ignore */ }
        throw new Error(errorDetail);
      }

      // --- Usar Toast para Sucesso ---
      toast.success('Contato adicionado com sucesso!');
      reset();
      onSuccess();

    } catch (error: any) {
      console.error("Error adding contact:", error);
      const errorMessage = error.message || "Ocorreu um erro inesperado.";
      setApiError(errorMessage); // Mantém o erro no formulário se necessário
      // --- Usar Toast para Erro ---
      toast.error(errorMessage);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {/* API Error Display (opcional, já que temos o toast) */}
      {apiError && (
        <p className="text-sm text-red-600 bg-red-100 p-2 rounded border border-red-300">
            {apiError}
        </p>
      )}

      {/* Name Field */}
      <div className="space-y-1">
        <Label htmlFor="name">Nome</Label>
        <Input id="name" {...register('name')} placeholder="Nome (opcional)" disabled={isSubmitting} />
        {errors.name && <p className="text-xs text-red-500">{errors.name.message}</p>}
      </div>

      {/* Phone Number Field */}
      <div className="space-y-1">
        <Label htmlFor="phone_number">Telefone</Label>
        <InputMask
          id="phone_number"
          mask="+55 (__) _____-____" // Adjusted mask for common mobile format
          placeholder="+55 (11) 98765-4321" // More descriptive placeholder
          replacement={{ '_': /\d/ }} // Use '9' for digits as per react-input-mask convention
          autoFocus
          {...register("phone_number", {
            setValueAs: (value: string) => value.replace(/\D/g, ''), // Removes all non-digits
          })}
          // Apply the same classes as the standard Input component
          className={cn(inputVariants)}
          disabled={isSubmitting}
          required
        />
        {/* <Input id="phone_number" {...register('phone_number')} placeholder="Ex: 5511987654321" disabled={isSubmitting} required /> */}
        {errors.phone_number && <p className="text-xs text-red-500">{errors.phone_number.message}</p>}
      </div>

      {/* Email Field */}
      <div className="space-y-1">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" {...register('email')} placeholder="email@exemplo.com (opcional)" disabled={isSubmitting} />
        {errors.email && <p className="text-xs text-red-500">{errors.email.message}</p>}
      </div>

      {/* Action Buttons */}
      <div className="flex justify-end gap-2 pt-2">
         {onCancel && (
             <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
                Cancelar
             </Button>
         )}
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Salvando...</>
          ) : ( 'Salvar Contato' )}
        </Button>
      </div>
    </form>
  );
};