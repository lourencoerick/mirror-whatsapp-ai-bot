// src/app/dashboard/overview/page.tsx
"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import {
  getDashboardMessageVolume,
  getDashboardStats,
} from "@/lib/api/dashboard"; // Nossa função API
import { components } from "@/types/api"; // Nossos tipos gerados
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
// ShadCN UI Components
import ConversationStatusPieChart from "@/app/dashboard/overview/_components/conversation-status-chart-pie";
import MessageVolumeLineChart from "@/app/dashboard/overview/_components/message-volume-chart";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"; // Para os KPIs
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { format, subDays } from "date-fns"; // date-fns para manipulação de datas
import { ptBR } from "date-fns/locale"; // Para localização, se necessário
import {
  AlertCircle,
  BotIcon,
  CalendarIcon,
  CheckCircleIcon,
  InboxIcon,
  Loader2,
  MessageSquareText,
  TrendingUp,
  Users,
} from "lucide-react"; // Ícones
import { DateRange } from "react-day-picker";

// Tipos locais
type DashboardStats = components["schemas"]["DashboardStatsResponse"];
type DashboardMessageVolume =
  components["schemas"]["DashboardMessageVolumeResponse"];

// Componente para os Scorecards/KPIs (vamos criar depois ou embutir)
interface PieChartDataItem {
  name: string;
  value: number;
  fill: string;
}

interface KPICardProps {
  title: string;
  value: string | number;
  icon?: React.ReactNode;
  description?: string;
}

const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  icon,
  description,
}) => (
  <Card>
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium">{title}</CardTitle>
      {icon}
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{value}</div>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
    </CardContent>
  </Card>
);

export default function DashboardOverviewPage() {
  const { setPageTitle } = useLayoutContext();
  useEffect(() => {
    setPageTitle("Visão Geral");
  }, [setPageTitle]);

  const fetcher = useAuthenticatedFetch();

  // Estado para o seletor de data
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 29), // Padrão: últimos 30 dias
    to: new Date(),
  });

  // TODO: Estado para selectedInboxId (se formos implementar o filtro de inbox)
  // const [selectedInboxId, setSelectedInboxId] = useState<string | undefined>();

  // Query para buscar os dados de estatísticas
  const {
    data: statsData,
    isLoading: isLoadingStats,
    isError: isErrorStats,
    error: errorStats,
    refetch: refetchStats,
  } = useQuery<DashboardStats, Error>({
    // Especificando tipo de erro como Error
    queryKey: [
      "dashboardStats",
      dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : "all",
      dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : "all",
      // selectedInboxId || "all", // Adicionar seletor de inbox
    ],
    queryFn: () => {
      if (!fetcher) throw new Error("Fetcher not available");
      if (!dateRange?.from || !dateRange?.to) {
        // Idealmente, o botão de aplicar filtro estaria desabilitado se as datas não estiverem setadas
        throw new Error("Período de datas inválido.");
      }
      return getDashboardStats(
        fetcher,
        format(dateRange.from, "yyyy-MM-dd"),
        format(dateRange.to, "yyyy-MM-dd")
        // selectedInboxId
      );
    },
    enabled: !!fetcher && !!dateRange?.from && !!dateRange?.to, // Habilitar query apenas se fetcher e datas estiverem prontos
    staleTime: 5 * 60 * 1000, // 5 minutos
    refetchOnWindowFocus: false,
  });

  const {
    data: volumeData,
    isLoading: isLoadingVolume,
    isError: isErrorVolume,
    error: errorVolume,
    refetch: refetchVolume,
  } = useQuery<DashboardMessageVolume, Error>({
    queryKey: [
      "dashboardMessageVolume",
      dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : "all",
      dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : "all",
      // selectedInboxId || "all", // Adicionar seletor de inbox
      "day", // Exemplo de granularidade, você pode tornar isso um estado
    ],
    queryFn: () => {
      if (!fetcher) throw new Error("Fetcher not available");
      if (!dateRange?.from || !dateRange?.to) {
        throw new Error("Período de datas inválido.");
      }
      return getDashboardMessageVolume(
        fetcher,
        format(dateRange.from, "yyyy-MM-dd"),
        format(dateRange.to, "yyyy-MM-dd"),
        "day" // Exemplo de granularidade, idealmente viria de um estado/seletor
        // selectedInboxId
      );
    },
    enabled: !!fetcher && !!dateRange?.from && !!dateRange?.to,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  // --- Preparar dados para o Gráfico de Pizza de Status de Conversas ---
  const conversationStatusDataForPie: PieChartDataItem[] =
    statsData?.conversation_stats
      ? [
          {
            name: "Pendentes",
            value: statsData.conversation_stats.pending_count,
            fill: "#FFC107",
          }, // Amarelo/Laranja Vibrante
          {
            name: "Com Bot",
            value: statsData.conversation_stats.bot_active_count,
            fill: "#4CAF50",
          }, // Verde Sucesso
          {
            name: "Com Humanos",
            value: statsData.conversation_stats.human_active_count,
            fill: "#2196F3",
          }, // Azul Confiável
          {
            name: "Abertas (Outras)",
            value: statsData.conversation_stats.open_active_count,
            fill: "#9E9E9E",
          }, // Cinza Neutro
        ].filter((item) => item.value > 0) // Opcional: não mostrar fatias com valor 0
      : [];

  const handleApplyFilters = () => {
    refetchStats();
    if (volumeData) refetchVolume(); // Só refetch se já tiver dados, ou ajuste a lógica de enabled
  };

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8 space-y-8">
      {" "}
      {/* Aumentado space-y */}
      {/* Seção de Filtros */}
      <div className="flex flex-col sm:flex-row gap-4 items-center pb-4 border-b">
        {" "}
        {/* Adicionado border-b */}
        <Popover>
          {/* ... (Popover do DatePicker como antes) ... */}
          <PopoverTrigger asChild>
            <Button
              id="date"
              variant={"outline"}
              className="w-full sm:w-[300px] justify-start text-left font-normal"
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {dateRange?.from ? (
                dateRange.to ? (
                  <>
                    {format(dateRange.from, "dd/MM/yy", { locale: ptBR })} -{" "}
                    {format(dateRange.to, "dd/MM/yy", { locale: ptBR })}
                  </>
                ) : (
                  format(dateRange.from, "dd/MM/yy", { locale: ptBR })
                )
              ) : (
                <span>Selecione um período</span>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              initialFocus
              mode="range"
              defaultMonth={dateRange?.from}
              selected={dateRange}
              onSelect={setDateRange}
              numberOfMonths={2}
              locale={ptBR}
              disabled={(date) =>
                date > new Date() || date < new Date("2000-01-01")
              }
            />
          </PopoverContent>
        </Popover>
        {/* TODO: Seletor de Inbox */}
        <Button
          onClick={handleApplyFilters}
          disabled={isLoadingStats || !dateRange?.from || !dateRange?.to}
        >
          {isLoadingStats ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : null}
          Aplicar Filtros
        </Button>
      </div>
      {/* Feedback de Carregamento ou Erro Global para os Dados */}
      {isLoadingStats && (
        <div className="flex items-center justify-center py-10">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="ml-3 text-muted-foreground">
            Carregando estatísticas...
          </p>
        </div>
      )}
      {isErrorStats && !isLoadingStats && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Erro ao Carregar Estatísticas</AlertTitle>
          <AlertDescription>
            {(errorStats as Error)?.message ||
              "Não foi possível buscar os dados do dashboard."}
          </AlertDescription>
        </Alert>
      )}
      {/* Conteúdo Principal do Dashboard (Scorecards e Gráficos) */}
      {!isLoadingStats && !isErrorStats && statsData && (
        <div className="space-y-8">
          {/* Seção: Atividade de Conversas */}
          <div>
            <h2 className="text-xl font-semibold mb-4">
              Atividade de Conversas (Atual)
            </h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <KPICard
                title="Conversas Ativas"
                value={statsData.conversation_stats.total_active_count}
                icon={
                  <MessageSquareText className="h-4 w-4 text-muted-foreground" />
                }
                description="Bot + Humano + Abertas"
              />
              <KPICard
                title="Pendentes"
                value={statsData.conversation_stats.pending_count}
                icon={<Loader2 className="h-4 w-4 text-muted-foreground" />}
                description="Aguardando primeira ação"
              />
              <KPICard
                title="Com Bot"
                value={statsData.conversation_stats.bot_active_count}
                icon={<BotIcon className="h-4 w-4 text-muted-foreground" />}
                description="Atualmente com o Vendedor IA"
              />
              <KPICard
                title="Com Humanos"
                value={statsData.conversation_stats.human_active_count}
                icon={<Users className="h-4 w-4 text-muted-foreground" />}
                description="Atualmente com a equipe"
              />
            </div>
          </div>

          <Separator />

          {/* Seção: Performance no Período */}
          <div>
            <h2 className="text-xl font-semibold mb-4">
              Performance no Período Selecionado
            </h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {" "}
              {/* Ajustado para 3 colunas */}
              <KPICard
                title="Novas Conversas"
                value={statsData.conversation_stats.new_in_period_count}
                icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
                description={`De ${format(
                  dateRange!.from!,
                  "dd/MM"
                )} a ${format(dateRange!.to!, "dd/MM")}`}
              />
              <KPICard
                title="Conversas Fechadas"
                value={statsData.conversation_stats.closed_in_period_count}
                icon={
                  <CheckCircleIcon className="h-4 w-4 text-muted-foreground" />
                }
                description="Total de conversas resolvidas"
              />
              {/* KPI para % Resolvidas pelo Bot (quando disponível) */}
              {statsData.conversation_stats.closed_in_period_count > 0 &&
                statsData.conversation_stats.closed_by_bot_in_period_count >=
                  0 && (
                  <KPICard
                    title="% Resolvidas pelo Bot"
                    // Evitar divisão por zero se closed_in_period_count for 0
                    value={`${(
                      (statsData.conversation_stats
                        .closed_by_bot_in_period_count /
                        statsData.conversation_stats.closed_in_period_count) *
                      100
                    ).toFixed(1)}%`}
                    icon={<BotIcon className="h-4 w-4 text-muted-foreground" />}
                    description="Das conversas fechadas no período"
                  />
                )}
            </div>
          </div>

          <Separator />

          {/* Seção: Atividade de Mensagens */}
          <div>
            <h2 className="text-xl font-semibold mb-4">
              Atividade de Mensagens (Período)
            </h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {" "}
              {/* Ajustado para 3 colunas */}
              <KPICard
                title="Msgs. Recebidas"
                value={statsData.message_stats.received_in_period_count}
                icon={<InboxIcon className="h-4 w-4 text-muted-foreground" />}
                description="Total de mensagens de entrada"
              />
              <KPICard
                title="Msgs. Enviadas (Bot)"
                value={statsData.message_stats.sent_by_bot_in_period_count}
                icon={<BotIcon className="h-4 w-4 text-muted-foreground" />}
                description="Total de mensagens automáticas"
              />
              <KPICard
                title="Msgs. Enviadas (Humanos)"
                value={statsData.message_stats.sent_by_human_in_period_count}
                icon={<Users className="h-4 w-4 text-muted-foreground" />}
                description="Total de mensagens manuais"
              />
            </div>
          </div>

          <Separator />

          {/* Seção: Configuração da Conta */}
          <div>
            <h2 className="text-xl font-semibold mb-4">
              Configuração da Conta
            </h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {" "}
              {/* Pode ser menos colunas aqui */}
              <KPICard
                title="Inboxes Ativas"
                value={statsData.active_inboxes_count}
                icon={<InboxIcon className="h-4 w-4 text-muted-foreground" />}
                description="Total de canais configurados"
              />
            </div>
          </div>

          {/* GRÁFICOS (a serem adicionados) */}
          <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-2 mt-8">
            {" "}
            {/* Adicionado mt-8 */}
            {/* Espaço para Gráfico de Status de Conversas */}
            <Card>
              <CardHeader>
                <CardTitle>Distribuição de Status (Atual)</CardTitle>
                <CardDescription>
                  Visão geral dos status das conversas ativas e pendentes.
                </CardDescription>
              </CardHeader>
              <CardContent className="h-[300px] md:h-[350px]">
                {conversationStatusDataForPie.length > 0 ? (
                  <ConversationStatusPieChart
                    data={conversationStatusDataForPie}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground">
                    Sem dados de status para exibir no gráfico.
                  </div>
                )}
              </CardContent>
            </Card>
            {/* Espaço para Gráfico de Volume de Mensagens */}
            <Card>
              <CardHeader>
                <CardTitle>Volume de Mensagens (Período)</CardTitle>
                <CardDescription>
                  Tendência de mensagens recebidas e enviadas.
                </CardDescription>
              </CardHeader>
              <CardContent className="h-[300px] md:h-[350px]">
                {isLoadingVolume ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : volumeData && volumeData.time_series.length > 0 ? (
                  <MessageVolumeLineChart
                    data={volumeData.time_series}
                    granularity={volumeData.granularity as "day" | "hour"}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground">
                    Sem dados de volume para exibir.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
