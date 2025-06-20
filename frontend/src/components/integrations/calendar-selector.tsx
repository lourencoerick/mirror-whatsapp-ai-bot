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
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { getGoogleCalendars } from "@/lib/api/google-calendar";
import { components } from "@/types/api";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

type CalendarResponse = components["schemas"]["CalendarResponse"];

interface CalendarSelectorProps {
  selectedValue: string | null | undefined;
  onValueChange: (value: string) => void;
  disabled?: boolean;
}

export function CalendarSelector({
  selectedValue,
  onValueChange,
  disabled,
}: CalendarSelectorProps) {
  const fetcher = useAuthenticatedFetch();
  const [calendars, setCalendars] = useState<CalendarResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCals = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getGoogleCalendars(fetcher);
        setCalendars(data);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } catch (err: any) {
        setError(err.message || "Falha ao buscar calendários.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchCals();
  }, [fetcher]);

  if (isLoading) {
    return (
      <div className="flex items-center text-sm">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Carregando
        calendários...
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  return (
    <div>
      <Label className="mb-1.5 block" htmlFor="calendar-select">
        Calendário para Agendamentos
      </Label>
      <Select
        onValueChange={onValueChange}
        defaultValue={selectedValue ?? ""}
        disabled={disabled}
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
