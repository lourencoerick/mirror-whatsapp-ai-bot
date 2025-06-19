// components/settings/WorkingHoursSelector.tsx
"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { components } from "@/types/api"; // <-- USAR ESTA
import { useEffect } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";

// Definir o tipo localmente para facilitar a leitura
type AvailabilityRule = components["schemas"]["AvailabilityRuleSchema"];
// --- NOVAS PROPS ---
interface WorkingHoursSelectorProps {
  value: AvailabilityRule[]; // Recebe o array de regras diretamente
  onChange: (value: AvailabilityRule[]) => void; // Notifica o pai com o novo array
  disabled?: boolean;
}

const daysOfWeek = [
  { id: 0, name: "Domingo" },
  { id: 1, name: "Segunda-feira" },
  { id: 2, name: "Terça-feira" },
  { id: 3, name: "Quarta-feira" },
  { id: 4, name: "Quinta-feira" },
  { id: 5, name: "Sexta-feira" },
  { id: 6, name: "Sábado" },
];

const timeOptions = Array.from({ length: 48 }, (_, i) => {
  const hours = Math.floor(i / 2)
    .toString()
    .padStart(2, "0");
  const minutes = i % 2 === 0 ? "00" : "30";
  return `${hours}:${minutes}`;
});

// O componente agora aceita 'value' e 'onChange' diretamente
export function WorkingHoursSelector({
  value,
  onChange,
  disabled,
}: WorkingHoursSelectorProps) {
  // O formulário interno agora é inicializado com o 'value' recebido via props.
  const { control, watch, reset } = useForm<{ rules: AvailabilityRule[] }>({
    defaultValues: {
      rules:
        value && value.length === 7
          ? value
          : daysOfWeek.map((day) => ({
              dayOfWeek: day.id,
              isEnabled: [1, 2, 3, 4, 5].includes(day.id),
              startTime: "09:00",
              endTime: "18:00",
            })),
    },
  });

  const { fields } = useFieldArray({
    control,
    name: "rules",
  });

  const watchedRules = watch("rules");

  // Efeito para propagar as mudanças para o formulário principal
  useEffect(() => {
    // Chama o onChange do pai com o novo array de regras
    onChange(watchedRules);
  }, [watchedRules, onChange]);

  // Efeito para resetar o formulário interno se o valor externo mudar
  useEffect(() => {
    if (value && value.length === 7) {
      reset({ rules: value });
    }
  }, [value, reset]);

  return (
    <div className="space-y-3">
      {fields.map((item, index) => {
        const dayName = daysOfWeek.find((d) => d.id === item.dayOfWeek)?.name;
        const isEnabled = watch(`rules.${index}.isEnabled`);

        return (
          <div
            key={item.id}
            className="grid grid-cols-3 items-center gap-4 p-2 border rounded-md"
          >
            {/* Coluna 1: Dia da Semana e Switch */}
            <div className="col-span-1 flex items-center space-x-3">
              <Controller
                name={`rules.${index}.isEnabled`}
                control={control}
                render={({ field: switchField }) => (
                  <Switch
                    id={`isenabled-${item.dayOfWeek}`}
                    checked={switchField.value}
                    onCheckedChange={switchField.onChange}
                    disabled={disabled}
                  />
                )}
              />
              <Label
                htmlFor={`isenabled-${item.dayOfWeek}`}
                className="font-medium"
              >
                {dayName}
              </Label>
            </div>

            {/* Coluna 2 e 3: Horários (condicional) */}
            {isEnabled ? (
              <div className="col-span-2 grid grid-cols-2 items-center gap-2">
                {/* Horário de Início */}
                <Controller
                  name={`rules.${index}.startTime`}
                  control={control}
                  render={({ field: selectField }) => (
                    <Select
                      onValueChange={selectField.onChange}
                      value={selectField.value}
                      disabled={disabled}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {timeOptions.map((time) => (
                          <SelectItem key={time} value={time}>
                            {time}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                {/* Horário de Fim */}
                <Controller
                  name={`rules.${index}.endTime`}
                  control={control}
                  render={({ field: selectField }) => (
                    <Select
                      onValueChange={selectField.onChange}
                      value={selectField.value}
                      disabled={disabled}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {timeOptions.map((time) => (
                          <SelectItem key={time} value={time}>
                            {time}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            ) : (
              <div className="col-span-2 text-sm text-muted-foreground text-center">
                Fechado
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
