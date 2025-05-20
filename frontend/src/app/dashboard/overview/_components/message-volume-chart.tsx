// src/components/dashboard/charts/MessageVolumeLineChart.tsx
"use client";

import { format, parseISO } from "date-fns"; // Para formatar as datas no eixo X
import { ptBR } from "date-fns/locale"; // Para localização
import React from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// O tipo de cada item na time_series, vindo da nossa API
interface TimeSeriesDataItem {
  timestamp: string; // ISO string date
  received_count: number;
  sent_by_bot_count: number;
  sent_by_human_count: number;
}

interface MessageVolumeLineChartProps {
  data: TimeSeriesDataItem[];
  granularity: "day" | "hour"; // Para formatar o eixo X corretamente
}

const MessageVolumeLineChart: React.FC<MessageVolumeLineChartProps> = ({
  data,
  granularity,
}) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
        Sem dados de volume de mensagens para exibir.
      </div>
    );
  }

  // Formatar os dados para o gráfico, especialmente o timestamp para o eixo X
  const chartData = data.map((item) => ({
    ...item,
    // Formatar o timestamp para exibição no eixo X
    // A Recharts pode usar o objeto Date diretamente, mas formatar aqui dá controle
    formattedTimestamp:
      granularity === "day"
        ? format(parseISO(item.timestamp), "dd/MM", { locale: ptBR })
        : format(parseISO(item.timestamp), "HH:mm", { locale: ptBR }),
    // Guardar o timestamp original para ordenação ou tooltips mais precisos se necessário
    originalTimestamp: parseISO(item.timestamp),
  }));

  // Custom Tooltip Content
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload; // O objeto de dados original do ponto
      const formattedDate =
        granularity === "day"
          ? format(dataPoint.originalTimestamp, "dd/MM/yyyy", { locale: ptBR })
          : format(dataPoint.originalTimestamp, "dd/MM/yyyy HH:mm", {
              locale: ptBR,
            });

      return (
        <div className="bg-background/90 backdrop-blur-sm p-3 shadow-lg rounded-md border text-sm">
          <p className="font-semibold mb-1">{formattedDate}</p>
          {payload.map((entry: any, index: number) => (
            <p key={`item-${index}`} style={{ color: entry.color }}>
              {`${entry.name}: ${entry.value}`}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart
        data={chartData}
        margin={{
          top: 5,
          right: 20, // Aumentado para não cortar labels da legenda
          left: 0, // Ajustado para dar espaço ao YAxis
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.2} />
        <XAxis
          dataKey="formattedTimestamp"
          tick={{ fontSize: 12, fill: "#666" }}
          stroke="#ccc"
          // interval="preserveStartEnd" // Para não cortar o primeiro e último label
          // Se houver muitos labels, pode adicionar:
          // tickFormatter={(tick) => { /* lógica para mostrar menos ticks */ }}
          // angle={-30} textAnchor="end" // Para rotacionar labels se forem muitos
        />
        <YAxis
          tick={{ fontSize: 12, fill: "#666" }}
          stroke="#ccc"
          allowDecimals={false} // Não mostrar decimais nas contagens
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          verticalAlign="top"
          height={36}
          wrapperStyle={{ right: 0 }} // Alinhar legenda à direita
        />
        <Line
          type="monotone"
          dataKey="received_count"
          name="Recebidas"
          stroke="#FFC107" // Azul
          strokeWidth={2}
          dot={{ r: 3, strokeWidth: 1, fill: "#fff" }}
          activeDot={{ r: 5, strokeWidth: 2 }}
        />
        <Line
          type="monotone"
          dataKey="sent_by_bot_count"
          name="Enviadas (Bot)"
          stroke="#4CAF50" // Verde
          strokeWidth={2}
          dot={{ r: 3, strokeWidth: 1, fill: "#fff" }}
          activeDot={{ r: 5, strokeWidth: 2 }}
        />
        <Line
          type="monotone"
          dataKey="sent_by_human_count"
          name="Enviadas (Humanos)"
          stroke="#2196F3" // Amarelo/Laranja
          strokeWidth={2}
          dot={{ r: 3, strokeWidth: 1, fill: "#fff" }}
          activeDot={{ r: 5, strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default MessageVolumeLineChart;
