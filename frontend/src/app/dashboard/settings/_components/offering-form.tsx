"use client";

import { components } from "@/types/api";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";

import { StringListInput } from "@/components/custom/single-list-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2 } from "lucide-react";

import {
  OfferingFormData,
  offeringValidationSchema,
} from "@/lib/validators/company-profile.schema";

type OfferingInfo = components["schemas"]["OfferingInfo"];

interface OfferingFormProps {
  initialData?: OfferingInfo | null;
  onSubmit: (data: OfferingFormData) => void;
  onCancel: () => void;
  isLoading: boolean;
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
      bonus_items: initialData?.bonus_items || [],
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

  const disabled = isSubmitting || isLoading;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="offering-name" className="mb-1.5 block">
          Nome da Oferta
        </Label>
        <Input id="offering-name" {...register("name")} disabled={disabled} />
        {errors.name && (
          <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>
        )}
      </div>
      <div>
        <Label htmlFor="offering-desc" className="mb-1.5 block">
          Descrição Simples
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
          Informação de Preço
        </Label>
        <Textarea
          id="offering-price"
          rows={2}
          placeholder="ex: A partir de R$XX, entre em contato"
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
          Link (Opcional)
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

      <div>
        <Controller
          name="key_features"
          control={control}
          render={({ field, fieldState: { error } }) => (
            <StringListInput
              field={field}
              label="Principais Características"
              id="offering-features"
              placeholder="Adicione um recurso..."
              error={error}
            />
          )}
        />
      </div>

      <div>
        <Controller
          name="bonus_items"
          control={control}
          render={({ field, fieldState: { error } }) => (
            <StringListInput
              field={field}
              label="Itens Bônus"
              id="offering-bonus"
              placeholder="Adicione um item bônus..."
              error={error}
            />
          )}
        />
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={disabled}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={disabled}>
          {disabled && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {initialData ? "Salvar Alterações" : "Adicionar Oferta"}
        </Button>
      </div>
    </form>
  );
}
