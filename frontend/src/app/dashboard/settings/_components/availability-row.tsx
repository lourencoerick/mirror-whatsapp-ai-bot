/* eslint-disable @typescript-eslint/no-explicit-any */
// components/settings/AvailabilityRow.tsx
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
import { useMemo } from "react"; // Importar useMemo para otimização
import { Control, Controller, useWatch } from "react-hook-form";

interface AvailabilityRowProps {
  control: Control<any>;
  index: number;
  dayName: string;
  dayId: number;
  disabled?: boolean;
}

// A lista completa de opções de tempo, gerada apenas uma vez.
const allTimeOptions = Array.from({ length: 48 }, (_, i) => {
  const hours = Math.floor(i / 2)
    .toString()
    .padStart(2, "0");
  const minutes = i % 2 === 0 ? "00" : "30";
  return `${hours}:${minutes}`;
});

export function AvailabilityRow({
  control,
  index,
  dayName,
  dayId,
  disabled,
}: AvailabilityRowProps) {
  const isEnabled = useWatch({
    control,
    name: `availability_rules.${index}.isEnabled`,
  });

  // --- LÓGICA PRINCIPAL ---
  // 1. Observamos o valor do startTime para esta linha específica.
  const startTimeValue = useWatch({
    control,
    name: `availability_rules.${index}.startTime`,
  });

  // 2. Usamos `useMemo` para calcular as opções de endTime apenas quando startTimeValue muda.
  // Isso é uma otimização de performance para evitar recalcular a cada renderização.
  const endTimeOptions = useMemo(() => {
    if (!startTimeValue) {
      // Se não houver hora de início, retorna todas as opções exceto a primeira (00:00)
      return allTimeOptions.slice(1);
    }
    // Filtra a lista de todas as opções, mantendo apenas aquelas que são
    // estritamente maiores que o startTime.
    return allTimeOptions.filter((time) => time > startTimeValue);
  }, [startTimeValue]);

  return (
    <div className="grid grid-cols-3 items-center gap-4 p-2 border rounded-md">
      {/* Coluna 1: Dia da Semana e Switch (sem alterações) */}
      <div className="col-span-1 flex items-center space-x-3">
        <Controller
          name={`availability_rules.${index}.isEnabled`}
          control={control}
          render={({ field: switchField }) => (
            <Switch
              id={`isenabled-${dayId}`}
              checked={switchField.value}
              onCheckedChange={switchField.onChange}
              disabled={disabled}
            />
          )}
        />
        <Label htmlFor={`isenabled-${dayId}`} className="font-medium">
          {dayName}
        </Label>
      </div>

      {/* Coluna 2 e 3: Horários (com a nova lógica) */}
      {isEnabled ? (
        <div className="col-span-2 grid grid-cols-2 items-center gap-2">
          {/* Horário de Início (sem alterações na renderização) */}
          <Controller
            name={`availability_rules.${index}.startTime`}
            control={control}
            render={({ field: selectField }) => (
              <Select
                onValueChange={selectField.onChange}
                value={String(selectField.value)}
                disabled={disabled}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {/* O último horário não pode ser selecionado como início */}
                  {allTimeOptions.slice(0, -1).map((time) => (
                    <SelectItem key={time} value={time}>
                      {time}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {/* Horário de Fim (agora usa as opções filtradas) */}
          <Controller
            name={`availability_rules.${index}.endTime`}
            control={control}
            render={({ field: selectField }) => (
              <Select
                onValueChange={selectField.onChange}
                value={String(selectField.value)}
                disabled={disabled}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {/* --- USA AS OPÇÕES FILTRADAS --- */}
                  {endTimeOptions.map((time) => (
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
}
