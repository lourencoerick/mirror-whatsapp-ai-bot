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
} from "recharts";

interface PieChartDataItem {
  name: string;
  value: number;
  fill: string;
}

interface ConversationStatusPieChartProps {
  data: PieChartDataItem[];
}

interface CustomizedLabelProps {
  cx: number;
  cy: number;
  midAngle: number;
  innerRadius: number;
  outerRadius: number;
  percent: number;
  index: number;
  value: number;
  name: string;
}

const renderCustomizedLabel = (props: CustomizedLabelProps) => {
  const { cx, cy, midAngle, innerRadius, outerRadius, percent } = props;

  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.6;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  if (percent * 100 < 5) {
    return null;
  }

  return (
    <text
      x={x}
      y={y}
      fill="#fff"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize="12px"
      fontWeight="bold"
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

// Definir o valor de innerRadius usado no <Pie> como uma constante ou variável
const PIE_INNER_RADIUS = "40%"; // Ou o valor que você está usando, ex: 0 para pizza sólida

const ConversationStatusPieChart: React.FC<ConversationStatusPieChartProps> = ({
  data,
}) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
        Sem dados para o gráfico.
      </div>
    );
  }

  const totalValue = data.reduce((sum, entry) => sum + entry.value, 0);

  // Determinar se é um Donut chart baseado no valor de PIE_INNER_RADIUS
  // Convertendo para número para a comparação (ex: "40%" -> 40, "0%" -> 0, 0 -> 0)
  const isDonutChart = parseFloat(String(PIE_INNER_RADIUS)) > 0;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={renderCustomizedLabel}
          outerRadius="80%"
          innerRadius={PIE_INNER_RADIUS} // Usar a constante/variável aqui
          fill="#8884d8"
          dataKey="value"
          nameKey="name"
          paddingAngle={data.length > 1 ? 2 : 0}
        >
          {data.map((entry) => (
            <Cell
              key={`cell-${entry.name}`}
              fill={entry.fill}
              stroke={entry.fill}
              strokeWidth={0.5}
            />
          ))}
          {/* Label central para o gráfico de Donut */}
          {totalValue > 0 &&
            isDonutChart && ( // << USAR isDonutChart AQUI
              <Label
                value={`${totalValue}`}
                position="center"
                fill="#333"
                fontSize="20px"
                fontWeight="bold"
                dy={-10}
              />
            )}
          {totalValue > 0 &&
            isDonutChart && ( // << USAR isDonutChart AQUI
              <Label
                value="Total"
                position="center"
                fill="#666"
                fontSize="12px"
                dy={10}
              />
            )}
        </Pie>
        <Tooltip
          formatter={(value: number, name: string, props) => {
            const itemPayload = props.payload as PieChartDataItem & {
              percent?: number;
            };
            const percentage = itemPayload?.percent
              ? `(${(itemPayload.percent * 100).toFixed(1)}%)`
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
