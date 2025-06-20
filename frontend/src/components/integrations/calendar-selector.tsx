// components/integrations/CalendarSelector.tsx
"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type components } from "@/types/api";

type Calendar = NonNullable<
  components["schemas"]["GoogleIntegrationStatus"]["calendars"]
>[number];

interface CalendarSelectorProps {
  selectedValue: string | null | undefined;
  onValueChange: (value: string) => void;
  calendars: Calendar[];
  disabled?: boolean;
}

export function CalendarSelector({
  selectedValue,
  onValueChange,
  calendars,
  disabled,
}: CalendarSelectorProps) {
  return (
    <div>
      <Label className="mb-1.5 block" htmlFor="calendar-select">
        Calendário para Agendamentos
      </Label>
      <Select
        onValueChange={onValueChange}
        value={selectedValue ?? ""}
        disabled={disabled || calendars.length === 0}
      >
        <SelectTrigger id="calendar-select">
          <SelectValue placeholder="Selecione um calendário..." />
        </SelectTrigger>
        <SelectContent>
          {calendars.map((cal) => (
            <SelectItem key={cal.id} value={cal.id}>
              {cal.summary}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground mt-1">
        A IA usará este calendário para verificar a disponibilidade e criar
        novos eventos.
      </p>
    </div>
  );
}
