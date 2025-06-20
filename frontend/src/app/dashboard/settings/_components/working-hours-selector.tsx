// components/settings/WorkingHoursSelector.tsx
"use client";

import { components } from "@/types/api";
import { Control } from "react-hook-form";
import { AvailabilityRow } from "./availability-row"; // Importar o novo componente

type AvailabilityRule = components["schemas"]["AvailabilityRuleSchema"];

interface WorkingHoursSelectorProps {
  fields: Array<Record<"id", string> & AvailabilityRule>;
  control: Control<any>;
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

export function WorkingHoursSelector({
  fields,
  control,
  disabled,
}: WorkingHoursSelectorProps) {
  return (
    <div className="space-y-3">
      {fields.map((item, index) => {
        const dayInfo = daysOfWeek.find((d) => d.id === item.dayOfWeek);
        if (!dayInfo) return null; // Segurança caso os dados estejam inconsistentes

        return (
          <AvailabilityRow
            key={item.id} // A chave continua aqui no loop
            control={control}
            index={index}
            dayName={dayInfo.name}
            dayId={dayInfo.id}
            disabled={disabled}
          />
        );
      })}
    </div>
  );
}
