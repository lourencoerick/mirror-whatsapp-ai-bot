import { useState } from "react";
import { getCountries, getCountryCallingCode, isValidPhoneNumber } from "libphonenumber-js";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { z } from "zod";
import { InputMask } from '@react-input/mask';
import { useInboxes } from "@/hooks/use-inboxes";
import { cn } from "@/lib/utils"
import { inputVariants } from '@/components/ui/input';

const countries = getCountries(); // ['BR', 'US', 'FR', ...]

const schema = z
  .object({
    country: z.string().default("BR"),
    number: z.string().min(8, "Digite o número de telefone"),
    inboxId: z.string().uuid("Selecione uma inbox válida"),
  })
  .refine(
    (data) => isValidPhoneNumber(data.number, data.country),
    {
      message: "Número inválido para o país selecionado",
      path: ["number"],
    }
  );

interface PhoneInputFormProps {
  onPhoneSubmit: (fullNumber: string, inboxId: string) => void;
  loadingText?: string;
  submitText?: string;
}

export default function PhoneInputForm({
  onPhoneSubmit,
  loadingText = "Iniciando...",
  submitText = "Iniciar"
}: PhoneInputFormProps) {
  const { register, handleSubmit, formState: { errors }, watch } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { country: "BR", number: "", inboxId: "" },
  });

  const [loading, setLoading] = useState(false);
  const selectedCountry = watch("country");

  const { inboxes, loading: inboxesLoading } = useInboxes();

  const onSubmit = (data: any) => {
    setLoading(true);
    const fullNumber = `${getCountryCallingCode(data.country)}${data.number}`;
    onPhoneSubmit(fullNumber, data.inboxId);
    setLoading(false);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <select {...register("inboxId")} className="border rounded p-2">
        <option value="">Selecione uma inbox</option>
        {inboxes.map((inbox) => (
          <option key={inbox.id} value={inbox.id}>
            {inbox.name} ({inbox.channel_type})
          </option>
        ))}
      </select>
      {errors.inboxId && (
        <span className="text-center text-red-500 text-sm">{errors.inboxId.message}</span>
      )}
      <div className="flex flex-row gap-2 text-sm text-center">
        <select {...register("country")} className="w-1/2 border rounded p-1">
          {countries.map((c) => (
            <option key={c} value={c}>
              +{getCountryCallingCode(c)} ({c})
            </option>
          ))}
        </select>
        {selectedCountry === "BR" ? (
          <InputMask
            id="number"
            mask="(__) _____-____" 
            placeholder="(11) 98765-4321" 
            replacement={{ '_': /\d/ }} 
            autoFocus
            {...register("number", {
              setValueAs: (value: string) => value.replace(/\D/g, ''), 
            })}
            className={cn(inputVariants)}
            required
          />
        ) : (
          <Input type="tel" placeholder="Digite o número" {...register("number")} />
        )}
      </div>
      {errors.number && (
        <span className="text-center text-red-500 text-sm">{errors.number.message}</span>
      )}



      <Button type="submit" disabled={loading || inboxesLoading}>
        {loading ? loadingText : submitText}
      </Button>
    </form>
  );
}
