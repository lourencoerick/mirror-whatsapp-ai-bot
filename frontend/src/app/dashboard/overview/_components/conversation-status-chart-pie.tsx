// src/components/dashboard/charts/ConversationStatusPieChart.tsx
"use client";

import React from "react";
import {
  Cell,
  Label,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts"; // Adicionado Sector e Label

interface PieChartDataItem {
  name: string;
  value: number;
  fill: string;
}

interface ConversationStatusPieChartProps {
  data: PieChartDataItem[];
}

// Função para renderizar um label customizado no centro (opcional, se quiser mostrar o total)
const renderCustomizedLabel = ({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
  index,
  value,
  name,
}) => {
  // Exemplo: se quiser mostrar o nome e percentual em cada fatia
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  if (percent * 100 < 5) return null; // Não mostrar label para fatias muito pequenas

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize="16px"
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

const ConversationStatusPieChart: React.FC<ConversationStatusPieChartProps> = ({
  data,
}) => {
  if (!data || data.length === 0) {
    // Este fallback pode ser tratado na página pai também, mas é bom ter aqui.
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
        Sem dados para o gráfico.
      </div>
    );
  }

  // Calcular o total para exibir no centro, se desejado
  const totalValue = data.reduce((sum, entry) => sum + entry.value, 0);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={renderCustomizedLabel} // Ativar se quiser labels nas fatias
          outerRadius="80%" // Usar percentual para melhor responsividade dentro do container
          innerRadius="40%" // Para criar um gráfico de "Donut" (Rosca)
          fill="#8884d8" // Cor padrão de fallback, será sobrescrita
          dataKey="value"
          nameKey="name"
          paddingAngle={data.length > 1 ? 2 : 0} // Pequeno espaço entre fatias se houver mais de uma
        >
          {data.map(
            (
              entry // Não precisa do index se a key for única (nome da entry)
            ) => (
              <Cell
                key={`cell-${entry.name}`}
                fill={entry.fill}
                stroke={entry.fill}
                strokeWidth={0.5}
              /> // Adicionado stroke para melhor definição
            )
          )}
          {/* Exemplo de Label no centro do Donut Chart (se innerRadius > 0) */}
          {totalValue > 0 && (
            <Label
              value={`${totalValue} Total`}
              position="center"
              fill="#333" // Cor do texto do label central
              fontSize="16px"
              fontWeight="bold"
            />
          )}
        </Pie>
        <Tooltip
          formatter={(value: number, name: string, props) => {
            // props.payload contém o objeto de dados original, incluindo a cor
            const percentage =
              props.payload && props.payload.percent
                ? `(${(props.payload.percent * 100).toFixed(1)}%)`
                : "";
            return [`${value} ${percentage}`, name];
          }}
          contentStyle={{
            backgroundColor: "white",
            borderRadius: "0.375rem",
            padding: "8px 12px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
          }}
          itemStyle={{ color: "#333" }}
        />
        <Legend
          layout="horizontal"
          verticalAlign="bottom"
          align="center"
          wrapperStyle={{ paddingTop: "20px" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
};

export default ConversationStatusPieChart;
