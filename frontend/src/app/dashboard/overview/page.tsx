// src/app/dashboard/overview/page.tsx
"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import {
  getDashboardMessageVolume,
  getDashboardStats,
} from "@/lib/api/dashboard";
import { fetchInboxes } from "@/lib/api/inbox";
import { components } from "@/types/api";
import { useQuery } from "@tanstack/react-query";
import { format, subDays } from "date-fns";
import { ptBR } from "date-fns/locale";
import {
  AlertCircle,
  BotIcon,
  CalendarIcon,
  CheckCircleIcon,
  InboxIcon as InboxIconLucide,
  Loader2,
  MessageSquareText,
  TrendingUp,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { DateRange } from "react-day-picker";
import ConversationStatusPieChart from "./_components/conversation-status-chart-pie";
import MessageVolumeLineChart from "./_components/message-volume-chart";

// Tipos locais
type DashboardStatsData = components["schemas"]["DashboardStatsResponse"];
type DashboardMessageVolumeData =
  components["schemas"]["DashboardMessageVolumeResponse"];
type InboxData = components["schemas"]["InboxRead"];

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

  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 29),
    to: new Date(),
  });
  const [selectedInboxId, setSelectedInboxId] = useState<string | undefined>(
    undefined
  );
  const [granularity, setGranularity] = useState<"day" | "hour">("day");

  const { data: inboxes, isLoading: isLoadingInboxes } = useQuery<
    InboxData[],
    Error
  >({
    queryKey: ["userInboxesList"],
    queryFn: () => {
      if (!fetcher) throw new Error("Fetcher not available for inboxes");
      return fetchInboxes(fetcher);
    },
    enabled: !!fetcher,
    staleTime: 15 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const formattedStartDate = dateRange?.from
    ? format(dateRange.from, "yyyy-MM-dd")
    : undefined;
  const formattedEndDate = dateRange?.to
    ? format(dateRange.to, "yyyy-MM-dd")
    : undefined;

  const {
    data: statsData,
    isLoading: isLoadingStats,
    isError: isErrorStats,
    error: errorStats,
    refetch: refetchStats,
  } = useQuery<DashboardStatsData, Error>({
    queryKey: [
      "dashboardStats",
      formattedStartDate,
      formattedEndDate,
      selectedInboxId || "all",
    ],
    queryFn: () => {
      if (!fetcher || !formattedStartDate || !formattedEndDate) {
        throw new Error("Fetcher or date range not available for stats.");
      }
      return getDashboardStats(
        fetcher,
        formattedStartDate,
        formattedEndDate,
        selectedInboxId === "all" ? undefined : selectedInboxId
      );
    },
    enabled: !!fetcher && !!formattedStartDate && !!formattedEndDate,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const {
    data: volumeData,
    isLoading: isLoadingVolume,
    isError: isErrorVolume,
    error: errorVolume,
    refetch: refetchVolume,
  } = useQuery<DashboardMessageVolumeData, Error>({
    queryKey: [
      "dashboardMessageVolume",
      formattedStartDate,
      formattedEndDate,
      selectedInboxId || "all",
      granularity,
    ],
    queryFn: () => {
      if (!fetcher || !formattedStartDate || !formattedEndDate) {
        throw new Error("Fetcher or date range not available for volume.");
      }
      return getDashboardMessageVolume(
        fetcher,
        formattedStartDate,
        formattedEndDate,
        granularity,
        selectedInboxId === "all" ? undefined : selectedInboxId
      );
    },
    enabled: !!fetcher && !!formattedStartDate && !!formattedEndDate,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const conversationStatusDataForPie: PieChartDataItem[] =
    statsData?.conversation_stats
      ? [
          {
            name: "Pendentes",
            value: statsData.conversation_stats.pending_count,
            fill: "#FFC107",
          },
          {
            name: "Com Bot",
            value: statsData.conversation_stats.bot_active_count,
            fill: "#4CAF50",
          },
          {
            name: "Com Humanos",
            value: statsData.conversation_stats.human_active_count,
            fill: "#2196F3",
          },
          {
            name: "Abertas (Outras)",
            value: statsData.conversation_stats.open_active_count,
            fill: "#9E9E9E",
          },
        ].filter((item) => item.value > 0)
      : [];

  const handleApplyFilters = () => {
    refetchStats();
    refetchVolume();
  };

  const globalIsLoading = isLoadingStats || isLoadingVolume || isLoadingInboxes;
  const globalIsError = isErrorStats || isErrorVolume;
  const globalError = errorStats || errorVolume;

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8 space-y-8">
      <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 items-center pb-4 border-b">
        {" "}
        {/* Ajustado gap */}
        <Popover>
          <PopoverTrigger asChild>
            <Button
              id="date"
              variant={"outline"}
              className="w-full sm:w-[280px] justify-start text-left font-normal"
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
                <span>Selecione</span>
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
        <Select
          value={selectedInboxId || "all"}
          onValueChange={(value) =>
            setSelectedInboxId(value === "all" ? undefined : value)
          }
          disabled={isLoadingInboxes || !inboxes}
        >
          <SelectTrigger className="w-full sm:w-[200px]">
            {" "}
            {/* Ajustado width */}
            <SelectValue
              placeholder={
                isLoadingInboxes ? "Carregando..." : "Todas as Inboxes"
              }
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas as Caixas</SelectItem>
            {inboxes?.map((inbox) => (
              <SelectItem key={inbox.id} value={inbox.id}>
                {inbox.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={granularity}
          onValueChange={(value) => setGranularity(value as "day" | "hour")}
        >
          <SelectTrigger className="w-full sm:w-[130px]">
            {" "}
            {/* Ajustado width */}
            <SelectValue placeholder="Granularidade" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="day">Diária</SelectItem>
            <SelectItem value="hour">Por Hora</SelectItem>
          </SelectContent>
        </Select>
        <Button
          onClick={handleApplyFilters}
          disabled={globalIsLoading || !dateRange?.from || !dateRange?.to}
          className="w-full sm:w-auto"
        >
          {globalIsLoading && !isLoadingInboxes ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : null}
          Aplicar
        </Button>
      </div>

      {globalIsLoading && (
        <div className="flex items-center justify-center py-10">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="ml-3 text-muted-foreground">
            Carregando dados do dashboard...
          </p>
        </div>
      )}

      {globalIsError && !globalIsLoading && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Erro ao Carregar Dados do Dashboard</AlertTitle>
          <AlertDescription>
            {(globalError as Error)?.message ||
              "Não foi possível buscar os dados."}
          </AlertDescription>
        </Alert>
      )}

      {!globalIsLoading && !globalIsError && statsData && (
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
          {/* Seção: Performance no Período Selecionado */}
          <div>
            <h2 className="text-xl font-semibold mb-4">
              Performance no Período Selecionado
            </h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <KPICard
                title="Novas Conversas"
                value={statsData.conversation_stats.new_in_period_count}
                icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
                description={`De ${
                  formattedStartDate
                    ? format(dateRange!.from!, "dd/MM", { locale: ptBR })
                    : ""
                } a ${
                  formattedEndDate
                    ? format(dateRange!.to!, "dd/MM", { locale: ptBR })
                    : ""
                }`}
              />
              <KPICard
                title="Conversas Fechadas"
                value={statsData.conversation_stats.closed_in_period_count}
                icon={
                  <CheckCircleIcon className="h-4 w-4 text-muted-foreground" />
                }
                description="Total de conversas resolvidas"
              />
              {statsData.conversation_stats.closed_in_period_count > 0 &&
                statsData.conversation_stats.closed_by_bot_in_period_count >=
                  0 && (
                  <KPICard
                    title="% Resolvidas pelo Bot"
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
          {/* Seção: Atividade de Mensagens (Período) */}
          <div>
            <h2 className="text-xl font-semibold mb-4">
              Atividade de Mensagens (Período)
            </h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <KPICard
                title="Msgs. Recebidas"
                value={statsData.message_stats.received_in_period_count}
                icon={
                  <InboxIconLucide className="h-4 w-4 text-muted-foreground" />
                }
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
              <KPICard
                title="Caixas de Entrada Ativas"
                value={statsData.active_inboxes_count}
                icon={
                  <InboxIconLucide className="h-4 w-4 text-muted-foreground" />
                }
                description="Total de canais configurados"
              />
            </div>
          </div>

          {/* GRÁFICOS */}
          <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-2 mt-8">
            <Card>
              <CardHeader>
                <CardTitle>Distribuição de Status (Atual)</CardTitle>
                <CardDescription>
                  Visão geral dos status das conversas ativas e pendentes.
                </CardDescription>
              </CardHeader>
              <CardContent className="h-[300px] md:h-[350px]">
                {isLoadingStats ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : conversationStatusDataForPie.length > 0 ? (
                  <ConversationStatusPieChart
                    data={conversationStatusDataForPie}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground">
                    Sem dados de status para exibir.
                  </div>
                )}
              </CardContent>
            </Card>
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
