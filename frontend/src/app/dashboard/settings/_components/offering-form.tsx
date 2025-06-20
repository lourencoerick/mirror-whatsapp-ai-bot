"use client";

import { components } from "@/types/api";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react"; // Importar useEffect
import { Controller, useForm } from "react-hook-form";

import { StringListInput } from "@/components/custom/single-list-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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
  isSchedulingFeatureEnabled: boolean;
}

export function OfferingForm({
  initialData,
  onSubmit,
  onCancel,
  isLoading,
  isSchedulingFeatureEnabled,
}: OfferingFormProps) {
  const form = useForm<OfferingFormData>({
    resolver: zodResolver(offeringValidationSchema),
    defaultValues: {
      id: initialData?.id,
      name: initialData?.name || "",
      short_description: initialData?.short_description || "",
      key_features: initialData?.key_features || [],
      bonus_items: initialData?.bonus_items || [],
      price: initialData?.price ?? null,
      price_info: initialData?.price_info || "",
      link: initialData?.link || "",
      requires_scheduling: initialData?.requires_scheduling || false,
      duration_minutes: initialData?.duration_minutes ?? null,
    },
  });

  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    watch,
    setValue,
  } = form;

  const requiresScheduling = watch("requires_scheduling");
  const disabled = isSubmitting || isLoading;

  // --- LÓGICA DE CONSISTÊNCIA ---
  // Efeito que observa se a feature principal de agendamento foi desativada.
  // Se foi, ele força o switch desta oferta para 'false'.
  useEffect(() => {
    if (!isSchedulingFeatureEnabled) {
      setValue("requires_scheduling", false);
    }
  }, [isSchedulingFeatureEnabled, setValue]);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 mx-4">
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
        <Label htmlFor="offering-price-value" className="mb-1.5 block">
          Preço (R$)
        </Label>
        <Input
          id="offering-price-value"
          type="number"
          step="0.01"
          min="0"
          placeholder="Ex: 29.90 (deixe em branco ou 0 se gratuito)"
          {...register("price", {
            setValueAs: (value) => {
              if (
                value === "" ||
                value === null ||
                value === undefined ||
                String(value).trim() === ""
              ) {
                return null;
              }
              const num = parseFloat(value);
              return isNaN(num) ? null : num;
            },
          })}
          disabled={disabled}
          className="w-full"
        />
        {errors.price && (
          <p className="text-xs text-red-600 mt-1">{errors.price.message}</p>
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

      {/* --- SEÇÃO DE AGENDAMENTO --- */}
      <div className="space-y-4 rounded-lg border p-4">
        <div className="space-y-1">
          <h3 className="text-base font-medium">Agendamento</h3>
          <p className="text-sm text-muted-foreground">
            Configure se esta oferta requer um agendamento para ser concluída.
          </p>
        </div>
        <div className="flex items-center space-x-2 pt-2">
          <Controller
            name="requires_scheduling"
            control={control}
            render={({ field }) => (
              <Switch
                id="requires-scheduling"
                checked={field.value}
                onCheckedChange={field.onChange}
                disabled={disabled || !isSchedulingFeatureEnabled}
              />
            )}
          />
          <Label
            htmlFor="requires-scheduling"
            className={
              !isSchedulingFeatureEnabled
                ? "text-muted-foreground cursor-not-allowed"
                : ""
            }
          >
            Requer agendamento
          </Label>
        </div>

        {/* Mensagem de ajuda que aparece quando a feature principal está desabilitada */}
        {!isSchedulingFeatureEnabled && (
          <p className="text-xs text-muted-foreground">
            Para habilitar esta opção, ative primeiro os agendamentos no perfil
            da empresa.
          </p>
        )}

        {/* O campo de duração agora também verifica se a feature principal está habilitada */}
        {requiresScheduling && isSchedulingFeatureEnabled && (
          <div className="pt-2">
            <Label htmlFor="duration-minutes" className="mb-1.5 block">
              Duração do Serviço (em minutos)
            </Label>
            <Input
              id="duration-minutes"
              type="number"
              min="1"
              placeholder="Ex: 45"
              {...register("duration_minutes", {
                setValueAs: (value) => {
                  if (value === "" || value === null || value === undefined)
                    return null;
                  const num = parseInt(value, 10);
                  return isNaN(num) ? null : num;
                },
              })}
              disabled={disabled}
            />
            {errors.duration_minutes && (
              <p className="text-xs text-red-600 mt-1">
                {errors.duration_minutes.message}
              </p>
            )}
          </div>
        )}
      </div>

      {/* --- Botões de Ação --- */}
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
