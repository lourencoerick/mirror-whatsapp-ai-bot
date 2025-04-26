// app/dashboard/settings/_components/OfferingForm.tsx
"use client";

import { components } from "@/types/api";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";

import { StringListInput } from "@/components/custom/single-list-input"; // Reutilizar!
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2 } from "lucide-react";

import {
  OfferingFormData,
  offeringValidationSchema,
} from "@/lib/validators/company-profile.schema";

// Tipo para uma única oferta (do schema gerado)
type OfferingInfo = components["schemas"]["OfferingInfo"];

interface OfferingFormProps {
  initialData?: OfferingInfo | null; // Dados para edição (null/undefined para criação)
  onSubmit: (data: OfferingFormData) => void; // Usar tipo importado para callback
  onCancel: () => void; // Callback para fechar modal/sheet
  isLoading: boolean; // Estado de carregamento externo (ex: do Dialog)
}

export function OfferingForm({
  initialData,
  onSubmit,
  onCancel,
  isLoading,
}: OfferingFormProps) {
  const form = useForm<OfferingFormData>({
    resolver: zodResolver(offeringValidationSchema),
    defaultValues: {
      name: initialData?.name || "",
      short_description: initialData?.short_description || "",
      key_features: initialData?.key_features || [],
      price_info: initialData?.price_info || "",
      link: initialData?.link || "",
    },
  });

  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = form;

  // Usa o isSubmitting interno OU o isLoading externo para desabilitar
  const disabled = isSubmitting || isLoading;

  return (
    // O form é submetido pelo botão dentro dele, não precisa da tag <form> aqui
    // se os botões estiverem fora (ex: no footer do Dialog/Sheet)
    // Mas vamos manter por enquanto para clareza.
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="offering-name" className="mb-1.5 block">
          Offering Name
        </Label>
        <Input id="offering-name" {...register("name")} disabled={disabled} />
        {errors.name && (
          <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>
        )}
      </div>
      <div>
        <Label htmlFor="offering-desc" className="mb-1.5 block">
          Short Description
        </Label>
        <Textarea
          id="offering-desc"
          rows={3}
          {...register("short_description")}
          disabled={disabled}
        />
        {errors.short_description && (
          <p className="text-xs text-red-600 mt-1">
            {errors.short_description.message}
          </p>
        )}
      </div>
      <div>
        <Label htmlFor="offering-price" className="mb-1.5 block">
          Price Info
        </Label>
        <Input
          id="offering-price"
          placeholder="e.g., Starts at $XX, Contact us"
          {...register("price_info")}
          disabled={disabled}
        />
        {errors.price_info && (
          <p className="text-xs text-red-600 mt-1">
            {errors.price_info.message}
          </p>
        )}
      </div>
      <div>
        <Label htmlFor="offering-link" className="mb-1.5 block">
          Link (Optional)
        </Label>
        <Input
          id="offering-link"
          type="url"
          placeholder="https://..."
          {...register("link")}
          disabled={disabled}
        />
        {errors.link && (
          <p className="text-xs text-red-600 mt-1">{errors.link.message}</p>
        )}
      </div>

      {/* Usar Controller para o StringListInput */}
      <div>
        <Controller
          name="key_features"
          control={control}
          render={({ field, fieldState: { error } }) => (
            <StringListInput
              field={field}
              label="Key Features"
              id="offering-features"
              placeholder="Add a feature..."
              error={error}
              // Passar disabled state? O StringListInput precisaria aceitar essa prop.
              // Por enquanto, não desabilitamos o input de lista.
            />
          )}
        />
      </div>

      {/* Botões podem ficar aqui ou no Footer do Dialog/Sheet */}
      <div className="flex justify-end space-x-2 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={disabled}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={disabled}>
          {disabled && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {initialData ? "Save Changes" : "Add Offering"}
        </Button>
      </div>
    </form>
  );
}
