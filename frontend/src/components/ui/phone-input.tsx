import { useState } from "react";
import { getCountries, getCountryCallingCode, isValidPhoneNumber } from "libphonenumber-js";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { z } from "zod";
import { InputMask } from '@react-input/mask';


const countries = getCountries(); // ['BR', 'US', 'FR', ...]

const schema = z
  .object({
    country: z.string().default("BR"),
    number: z.string().min(8, "Digite o número de telefone"),
  })
  .refine(
    (data) => isValidPhoneNumber(data.number, data.country),
    {
      message: "Número inválido para o país selecionado",
      path: ["number"],
    }
  );

interface PhoneInputFormProps {
  onPhoneSubmit: (fullNumber: string) => void;
  loadingText?: string;
  submitText?: string;
}

export default function PhoneInputForm({
  onPhoneSubmit,
  loadingText = "Iniciando...",
  submitText = "Iniciar"
}: PhoneInputFormProps) {
  const { register, handleSubmit, formState: { errors }, watch} = useForm({
    resolver: zodResolver(schema),
    defaultValues: { country: "BR", number: "" },
  });

  const [loading, setLoading] = useState(false);
  const selectedCountry = watch("country");


  const onSubmit = (data: any) => {
    setLoading(true);
    const fullNumber = `${getCountryCallingCode(data.country)}${data.number}`;
    onPhoneSubmit(fullNumber);
    setLoading(false);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <div className="flex flex-row gap-2 text-sm text-center">
        <select {...register("country")}>
          {countries.map((c) => (
            <option key={c} value={c}>
              +{getCountryCallingCode(c)} ({c})
            </option>
          ))}
        </select>
        {selectedCountry === "BR" ? (
          <InputMask
            mask="(__) _____-____"
            placeholder="Digite o número"
            replacement={{ _: /\d/ }}
            autoFocus
            {...register("number", {
              setValueAs: (value) => value.replace(/\D/g, ''),
            })}
            className="w-full text-md h-9 border-1 border-gray-200 rounded-md"
            style={{ paddingLeft: "1rem" }}
          />
        ) : (
          <Input type="tel" placeholder="Digite o número" {...register("number")} />
        )}
      </div>
      {errors.number && (
        <span className="text-center text-red-500 text-sm">{errors.number.message}</span>
      )}
      <Button type="submit" disabled={loading}>
        {loading ? loadingText : submitText}
      </Button>
    </form>
  );
}
