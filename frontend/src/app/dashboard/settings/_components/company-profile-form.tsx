// app/dashboard/settings/_components/CompanyProfileForm.tsx
"use client";
import { GuidelineInput } from "@/components/custom/guideline-input"; // Custom input for guidelines
import { StringListInput } from "@/components/custom/single-list-input"; // Custom input for string lists
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { formatCurrencyBRL } from "@/lib/utils/currency-utils";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertTriangle,
  Loader2,
  Pencil,
  PlusCircle,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { toast } from "sonner"; // For user notifications
// UI Components
import { CalendarSelector } from "@/components/integrations/calendar-selector";
import { GoogleCalendarConnectButton } from "@/components/integrations/google-calendar-connect-button";
import { ReauthorizeGoogleButton } from "@/components/integrations/reauhorize-google-button";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider, // Ensure TooltipProvider wraps Tooltip usage if not already higher up
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { FetchFunction } from "@/hooks/use-authenticated-fetch"; // Authenticated fetch hook type
import { updateCompanyProfile } from "@/lib/api/company-profile"; // API function for updating profile
import {
  CompanyProfileFormData,
  companyProfileValidationSchema,
  getDefaultAvailabilityRules,
} from "@/lib/validators/company-profile.schema"; // Zod schema and type
import { useUser } from "@clerk/nextjs";

import { components } from "@/types/api"; // API type definitions

import { JSX } from "react/jsx-runtime";
import { OfferingForm } from "./offering-form"; // Sub-form for offerings
import { WorkingHoursSelector } from "./working-hours-selector";

import { getGoogleIntegrationStatus } from "@/lib/api/google-calendar";
import { useQuery } from "@tanstack/react-query";

// Type definitions from the generated API specification
type CompanyProfileSchemaOutput =
  components["schemas"]["CompanyProfileSchema-Output"];
type OfferingInfo = components["schemas"]["OfferingInfo"];
type AvailabilityRule = components["schemas"]["AvailabilityRuleSchema"];

/**
 * Props for the CompanyProfileForm component.
 */
interface CompanyProfileFormProps {
  /** Initial company profile data to populate the form. Null if no data exists yet. */
  initialData: CompanyProfileSchemaOutput | null;
  /** Authenticated fetch function for making API calls. */
  fetcher: FetchFunction;
  /** Callback function triggered when the profile is successfully updated. */
  onProfileUpdate: (updatedProfile: CompanyProfileSchemaOutput) => void;
  /** Flag indicating if background research is in progress, disabling the form. */
  isResearching: boolean;
  /** Callback function triggered when the form's dirty state changes. */
  onDirtyChange: (isDirty: boolean) => void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const formatRules = (rules: any[] | null | undefined): AvailabilityRule[] => {
  if (!rules || rules.length !== 7) {
    return getDefaultAvailabilityRules();
  }
  return rules.map((rule) => ({
    ...rule,
    // Garante que startTime e endTime estejam no formato HH:mm
    startTime: rule.startTime ? rule.startTime.substring(0, 5) : "09:00",
    endTime: rule.endTime ? rule.endTime.substring(0, 5) : "18:00",
  }));
};

/**
 * Renders a form for editing the company's profile information,
 * including basic details, AI configuration, communication guidelines,
 * and offerings (products/services).
 * @param {CompanyProfileFormProps} props - The component props.
 * @returns {JSX.Element} The rendered form component.
 */
export function CompanyProfileForm({
  initialData,
  fetcher,
  onProfileUpdate,
  isResearching,
  onDirtyChange,
}: CompanyProfileFormProps): JSX.Element {
  const { user } = useUser();

  const { data: googleStatus, isLoading: isLoadingStatus } = useQuery({
    queryKey: ["googleIntegrationStatus"],
    queryFn: () => getGoogleIntegrationStatus(fetcher),
    // Só executa a query se o usuário estiver logado
    enabled: !!user,
  });

  const form = useForm<CompanyProfileFormData>({
    resolver: zodResolver(companyProfileValidationSchema), // Use Zod for validation
    defaultValues: {
      // Pre-populate the form with initial data or defaults (in pt-BR where applicable)

      company_name: initialData?.company_name || "",
      website: initialData?.website || "",
      address: initialData?.address || "",
      business_description: initialData?.business_description || "",
      target_audience: initialData?.target_audience || "",
      sales_tone:
        initialData?.sales_tone || "amigável, prestativo e profissional", // Default tone in pt-BR
      language: initialData?.language || "pt-BR", // Default language
      communication_guidelines: initialData?.communication_guidelines || [
        "BUSQUE sempre fazer perguntas esclarecedoras",
        "EVITE inventar informações que não foram fornecidas",
      ],
      ai_objective:
        initialData?.ai_objective ||
        "Engajar clientes, responder perguntas sobre ofertas e guiá-los para uma compra ou próximo passo.", // Default objective in pt-BR
      key_selling_points: initialData?.key_selling_points || [],
      accepted_payment_methods: initialData?.accepted_payment_methods || [],
      delivery_options: initialData?.delivery_options || [],
      opening_hours: initialData?.opening_hours || "",
      fallback_contact_info: initialData?.fallback_contact_info || "",
      is_scheduling_enabled: initialData?.is_scheduling_enabled || false,
      scheduling_calendar_id: initialData?.scheduling_calendar_id || null,
      availability_rules: formatRules(initialData?.availability_rules),
      offering_overview: initialData?.offering_overview || [], // Initialize offerings array
      // Do not include non-editable fields like ID or profile_version here
    },
  });

  const {
    control, // Needed for Controller components (integrating UI libs with RHF)
    register, // For standard HTML inputs
    handleSubmit, // Form submission handler
    formState: { errors, isSubmitting, isDirty }, // Form state for errors and loading
    reset, // Function to reset form values
    watch,
  } = form;

  // --- Google Calendar  ---
  const isSchedulingEnabled = watch("is_scheduling_enabled"); // Observa o valor do switch

  // --- Offerings Management State ---
  // `useFieldArray` manages the dynamic list of offerings within the form state
  const {
    fields: offerings, // Array of offering fields managed by RHF
    append, // Function to add a new offering
    remove, // Function to remove an offering
    update, // Function to update an existing offering
  } = useFieldArray({
    control,
    name: "offering_overview", // Must match the field name in the Zod schema/FormData
    keyName: "fieldId", // Optional: Use a different property name for React keys if 'id' conflicts
  });

  // State for controlling the offering add/edit modal (Dialog)
  const [isOfferingModalOpen, setIsOfferingModalOpen] = useState(false);
  // State to track the index of the offering being edited (null for new offering)
  const [editingOfferingIndex, setEditingOfferingIndex] = useState<
    number | null
  >(null);
  // State to hold the data passed to the OfferingForm when editing
  const [offeringFormData, setOfferingFormData] = useState<OfferingInfo | null>(
    null
  );

  // Effect to reset the form when initialData changes (e.g., after research completes)
  useEffect(() => {
    if (initialData) {
      reset({
        company_name: initialData.company_name || "",
        website: initialData.website || "",
        address: initialData.address || "",
        business_description: initialData.business_description || "",
        target_audience: initialData.target_audience || "",
        sales_tone:
          initialData.sales_tone || "amigável, prestativo e profissional",
        language: initialData.language || "pt-BR",
        communication_guidelines: initialData.communication_guidelines || [],
        ai_objective:
          initialData.ai_objective ||
          "Engajar clientes, responder perguntas sobre ofertas e guiá-los para uma compra ou próximo passo.",
        key_selling_points: initialData.key_selling_points || [],
        accepted_payment_methods: initialData.accepted_payment_methods || [],
        delivery_options: initialData.delivery_options || [],
        offering_overview: initialData.offering_overview || [],
        opening_hours: initialData.opening_hours || "",
        fallback_contact_info: initialData.fallback_contact_info || "",
        is_scheduling_enabled: initialData?.is_scheduling_enabled || false,
        scheduling_calendar_id: initialData?.scheduling_calendar_id || null,
        availability_rules: formatRules(initialData?.availability_rules),
      });
    }
  }, [initialData, reset]);

  useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  /** Opens the modal to add a new offering. */
  const handleAddNewOffering = () => {
    setEditingOfferingIndex(null); // Indicate new offering mode
    setOfferingFormData(null); // Clear any previous editing data
    setIsOfferingModalOpen(true);
  };

  /**
   * Opens the modal to edit an existing offering.
   * @param {number} index - The index of the offering to edit in the `offerings` array.
   */
  const handleEditOffering = (index: number) => {
    setEditingOfferingIndex(index);
    // Get the current data for the offering at the specified index
    setOfferingFormData(offerings[index] as OfferingInfo);
    setIsOfferingModalOpen(true);
  };

  /**
   * Removes an offering from the list.
   * @param {number} index - The index of the offering to remove.
   */
  const handleRemoveOffering = (index: number) => {
    remove(index); // Remove from react-hook-form's field array
    toast.info("Oferta removida.");
  };

  /**
   * Callback function triggered when the OfferingForm (in the modal) is submitted.
   * Updates or appends the offering data to the main form's state.
   * @param {OfferingInfo} data - The data submitted from the OfferingForm.
   */
  const handleSaveOffering = (data: OfferingInfo) => {
    if (editingOfferingIndex !== null) {
      const originalOfferingId = offerings[editingOfferingIndex].id;
      // Criamos o objeto de dados para salvar, garantindo que o ID original seja mantido.
      const dataToUpdate = {
        ...data,
        id: originalOfferingId,
        key_features: data.key_features || [],
        bonus_items: data.bonus_items || [],
      };

      update(editingOfferingIndex, dataToUpdate);
      toast.success("Oferta atualizada.");
    } else {
      const dataToAppend = {
        ...data,
        key_features: data.key_features || [],
        bonus_items: data.bonus_items || [],
      };
      append(dataToAppend);
      toast.success("Oferta adicionada.");
    }
    setIsOfferingModalOpen(false);
    setEditingOfferingIndex(null);
    setOfferingFormData(null);
  };

  /**
   * Handles the main form submission.
   * Sends the updated company profile data to the backend API.
   * Shows success or error notifications.
   * @param {CompanyProfileFormData} formData - The validated form data.
   */
  const onSubmit = async (formData: CompanyProfileFormData) => {
    console.log("Dados do formulário enviados:", formData);
    try {
      // Construct the payload for the API update request.
      // Include existing non-editable data (like ID, version) if available.
      const payload: CompanyProfileSchemaOutput = {
        ...(initialData || {}), // Spread existing data first
        ...formData, // Spread form data to overwrite editable fields
        // Ensure array fields are sent as empty arrays `[]` if they are empty/null/undefined
        communication_guidelines: formData.communication_guidelines || [],
        key_selling_points: formData.key_selling_points || [],
        delivery_options: formData.delivery_options || [],
        offering_overview: formData.offering_overview || [],
        // Ensure required fields from the schema (like profile_version) are present
        profile_version: initialData?.profile_version || 1, // Maintain existing version or default to 1
        // id, account_id, created_at, updated_at should be included from initialData if they exist
      };

      const updatedProfile = await updateCompanyProfile(fetcher, payload);

      if (updatedProfile) {
        toast.success("Sucesso!", {
          description: "Perfil da empresa atualizado com sucesso.",
        });
        onProfileUpdate(updatedProfile); // Notify parent component of the update
      } else {
        // This case should ideally be handled by the API function throwing an error
        throw new Error(
          "A função de atualização retornou nulo inesperadamente."
        );
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (error: any) {
      console.error("Falha ao atualizar perfil:", error);
      toast.error("Erro ao atualizar perfil", {
        description: error.message || "Ocorreu um erro inesperado.",
      });
    }
  };

  // Disable the entire form if submitting or if background research is active
  const formDisabled = isSubmitting || isResearching;

  const { fields } = useFieldArray({
    control,
    name: "availability_rules",
  });

  // --- ADICIONE ESTE CONSOLE.LOG DE DEPURAÇÃO ---
  console.log(
    "CompanyProfileForm: O que está sendo passado para WorkingHoursSelector?",
    { fields }
  );

  return (
    // Wrap Tooltip usage in a provider if not already present higher up the tree
    <TooltipProvider>
      <Card>
        <CardHeader>
          <CardTitle>Detalhes do Perfil da Empresa</CardTitle>

          <CardDescription>
            Edite as informações principais sobre sua empresa. Estes dados são
            usados pelo Vendedor IA.
            {isResearching && (
              <span className="ml-2 font-semibold text-blue-600">
                (Pesquisa em andamento...)
              </span>
            )}
            {isDirty && !isSubmitting && (
              <span className="text-sm text-yellow-600 mr-auto flex items-center">
                <AlertTriangle className="h-4 w-4 mr-1" />
                Existem alterações não salvas.
              </span>
            )}
          </CardDescription>
        </CardHeader>
        {/* Disable all fields within the fieldset when formDisabled is true */}
        <fieldset disabled={formDisabled}>
          <form onSubmit={handleSubmit(onSubmit)}>
            <CardContent className="space-y-6">
              {/* --- Basic Info Fields --- */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="mb-1.5 block" htmlFor="company_name">
                    Nome da Empresa
                  </Label>
                  <Input id="company_name" {...register("company_name")} />
                  {errors.company_name && (
                    <p className="text-xs text-red-600 mt-1">
                      {errors.company_name.message}
                    </p>
                  )}
                </div>
                <div>
                  <Label className="mb-1.5 block" htmlFor="website">
                    URL do Website
                  </Label>
                  <Input
                    id="website"
                    type="url"
                    placeholder="https://..."
                    {...register("website")}
                  />
                  {errors.website && (
                    <p className="text-xs text-red-600 mt-1">
                      {errors.website.message}
                    </p>
                  )}
                </div>
              </div>

              <div>
                <Label className="mb-1.5 block" htmlFor="business_description">
                  Descrição do Negócio
                </Label>
                <Textarea
                  id="business_description"
                  rows={4}
                  placeholder="Descreva o que sua empresa faz, seus principais produtos/serviços e o que a torna única."
                  {...register("business_description")}
                />
                {errors.business_description && (
                  <p className="text-xs text-red-600 mt-1">
                    {errors.business_description.message}
                  </p>
                )}
              </div>

              {/* --- AI Configuration Fields --- */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="mb-1.5 block" htmlFor="sales_tone">
                    Tom de Vendas da IA
                  </Label>
                  <Input
                    id="sales_tone"
                    placeholder="Ex: amigável, profissional, direto"
                    {...register("sales_tone")}
                  />
                  {errors.sales_tone && (
                    <p className="text-xs text-red-600 mt-1">
                      {errors.sales_tone.message}
                    </p>
                  )}
                </div>
                <div>
                  <Label className="mb-1.5 block" htmlFor="language">
                    Idioma Principal
                  </Label>
                  {/* TODO: Replace with a Shadcn Select component for better UX */}
                  <Input
                    id="language"
                    placeholder="Ex: pt-BR, en-US"
                    {...register("language")}
                  />
                  {errors.language && (
                    <p className="text-xs text-red-600 mt-1">
                      {errors.language.message}
                    </p>
                  )}
                </div>
              </div>

              <div>
                <Label className="mb-1.5 block" htmlFor="ai_objective">
                  Objetivo da IA
                </Label>
                <Textarea
                  id="ai_objective"
                  rows={3}
                  placeholder="Descreva o que a IA deve fazer (ex: qualificar leads, agendar demos, vender produtos)."
                  {...register("ai_objective")}
                />
                {errors.ai_objective && (
                  <p className="text-xs text-red-600 mt-1">
                    {errors.ai_objective.message}
                  </p>
                )}
              </div>

              {/* --- Custom Input Fields --- */}
              {/* Communication Guidelines using GuidelineInput component */}
              <div>
                <Controller
                  name="communication_guidelines"
                  control={control}
                  render={({ field, fieldState: { error } }) => (
                    <GuidelineInput
                      field={field}
                      label="Diretrizes de Comunicação (O que fazer/Não fazer)"
                      id="communication_guidelines"
                      placeholder="Digite uma diretriz (ex: sempre perguntar para esclarecer dúvidas)"
                      error={error}
                    />
                  )}
                />
              </div>

              {/* Key Selling Points using StringListInput component */}
              <div>
                <Controller
                  name="key_selling_points"
                  control={control}
                  render={({ field, fieldState: { error } }) => (
                    <StringListInput
                      field={field}
                      label="Principais Pontos de Venda (Diferenciais)"
                      id="key_selling_points"
                      placeholder="Adicione um ponto de venda..."
                      error={error}
                    />
                  )}
                />
              </div>

              {/* Key Payment Methods using StringListInput component */}
              <div>
                <Controller
                  name="accepted_payment_methods"
                  control={control}
                  render={({ field, fieldState: { error } }) => (
                    <StringListInput
                      field={field}
                      label="Métodos de Pagamento"
                      id="accepted_payment_methods"
                      placeholder="Adicione os métodos de pagamento aceito..."
                      error={error}
                    />
                  )}
                />
              </div>

              {/* Delivery Options using StringListInput component */}
              <div>
                <Controller
                  name="delivery_options"
                  control={control}
                  render={({ field, fieldState: { error } }) => (
                    <StringListInput
                      field={field}
                      label="Opções de Entrega/Retirada"
                      id="delivery_options"
                      placeholder="Adicione uma opção..."
                      error={error}
                    />
                  )}
                />
              </div>

              {/* --- Scheduling section --- */}
              <div className="space-y-4 rounded-lg border p-4">
                <div className="space-y-1">
                  <h3 className="text-lg font-medium">
                    Agendamentos via Google Calendar
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Permita que a IA agende compromissos diretamente na sua
                    agenda do Google.
                  </p>
                </div>

                {/* 1. Switch para Habilitar/Desabilitar a feature */}
                <div className="flex items-center space-x-2">
                  <Controller
                    name="is_scheduling_enabled"
                    control={control}
                    render={({ field }) => (
                      <Switch
                        id="is_scheduling_enabled"
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    )}
                  />
                  <Label htmlFor="is_scheduling_enabled">
                    Habilitar agendamentos
                  </Label>
                </div>

                {/* 2. Conteúdo condicional que aparece se a feature estiver habilitada */}
                {isSchedulingEnabled && (
                  <div className="space-y-4 pt-4 border-t">
                    {/* --- Bloco de Conexão com o Google --- */}
                    <div className="p-3 border rounded-md bg-slate-50/50">
                      <h4 className="font-medium mb-2">
                        1. Conecte sua Agenda
                      </h4>

                      {isLoadingStatus && (
                        <div>Verificando status da conexão...</div>
                      )}

                      {/* Estado 1: Não conectado */}
                      {googleStatus && !googleStatus.is_connected && (
                        <GoogleCalendarConnectButton />
                      )}

                      {/* Estado 2: Conectado, mas sem permissões */}
                      {googleStatus &&
                        googleStatus.is_connected &&
                        !googleStatus.has_all_permissions && (
                          <ReauthorizeGoogleButton />
                        )}

                      {/* Estado 3: Tudo certo! */}
                      {googleStatus &&
                        googleStatus.is_connected &&
                        googleStatus.has_all_permissions && (
                          <div>
                            <p className="text-sm text-green-700 mb-2">
                              ✅ Google Calendar Conectado com todas as
                              permissões.
                            </p>
                            <Controller
                              name="scheduling_calendar_id"
                              control={control}
                              render={({ field }) => (
                                <CalendarSelector
                                  selectedValue={field.value}
                                  onValueChange={field.onChange}
                                  disabled={formDisabled}
                                  calendars={googleStatus.calendars || []}
                                />
                              )}
                            />
                          </div>
                        )}
                    </div>

                    {/* --- Bloco de Configuração de Horários --- */}
                    <div className="p-3 border rounded-md bg-slate-50/50">
                      <h4 className="font-medium mb-2">
                        2. Defina sua Disponibilidade
                      </h4>
                      <Accordion
                        type="single"
                        collapsible
                        className="w-full"
                        defaultValue="item-1"
                      >
                        <AccordionItem value="item-1">
                          <AccordionTrigger>
                            Horários para Agendamento
                          </AccordionTrigger>
                          <AccordionContent className="pt-4">
                            <p className="text-sm text-muted-foreground mb-4">
                              Defina os dias e horários em que você está
                              disponível. A IA usará estas regras para oferecer
                              horários aos seus clientes.
                            </p>
                            {/* A CHAMADA CORRETA: Sem Controller, passando as props certas */}
                            <WorkingHoursSelector
                              fields={fields}
                              control={control}
                              disabled={formDisabled}
                            />

                            {/* O erro agora precisa ser lido do objeto de erros do formulário */}
                            {errors.availability_rules && (
                              <p className="text-xs text-red-600 mt-2">
                                {errors.availability_rules.root?.message ||
                                  errors.availability_rules.message ||
                                  "Erro nas regras de disponibilidade."}
                              </p>
                            )}
                          </AccordionContent>
                        </AccordionItem>
                      </Accordion>
                    </div>
                  </div>
                )}
              </div>

              {/* --- Offerings Section (Table + Modal) --- */}
              <div className="space-y-2 pt-2">
                <Label className="mb-1.5 block">
                  Ofertas (Produtos/Serviços/Planos)
                </Label>
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-base font-medium">
                      Ofertas Atuais
                    </CardTitle>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={handleAddNewOffering}
                    >
                      <PlusCircle className="mr-2 h-4 w-4" /> Adicionar Oferta
                    </Button>
                  </CardHeader>
                  <CardContent className="p-0">
                    {offerings.length === 0 ? (
                      <p className="text-sm text-muted-foreground italic text-center py-6 px-6">
                        Nenhuma oferta adicionada ainda. Clique em
                        &quot;Adicionar Oferta&quot;.
                      </p>
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-[30%]">Nome</TableHead>
                            <TableHead className="hidden md:table-cell w-[35%]">
                              Descrição Curta
                            </TableHead>
                            <TableHead className="w-[20%]">Preço</TableHead>
                            <TableHead className="text-right w-[15%]">
                              Ações
                            </TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {offerings.map((offering, index) => (
                            <TableRow key={offering.id}>
                              {/* Use field.id generated by useFieldArray for stable keys */}
                              <TableCell className="font-medium">
                                {offering.name}
                              </TableCell>
                              <TableCell className="hidden md:table-cell text-sm text-muted-foreground max-w-xs">
                                {offering.short_description ? (
                                  <Tooltip delayDuration={300}>
                                    <TooltipTrigger asChild>
                                      <span className="block truncate">
                                        {offering.short_description}
                                      </span>
                                    </TooltipTrigger>
                                    <TooltipContent side="top" align="start">
                                      <p className="max-w-xs break-words whitespace-pre-wrap">
                                        {offering.short_description}
                                      </p>
                                    </TooltipContent>
                                  </Tooltip>
                                ) : (
                                  <span className="text-muted-foreground/70">
                                    -
                                  </span> // Display hyphen if no description
                                )}
                              </TableCell>
                              <TableCell className="max-w-[150px] lg:max-w-[200px]">
                                {offering.price ? (
                                  <Tooltip delayDuration={300}>
                                    <TooltipTrigger asChild>
                                      <span className="block truncate">
                                        {formatCurrencyBRL(offering.price)}
                                      </span>
                                    </TooltipTrigger>
                                    <TooltipContent side="top" align="start">
                                      <p className="max-w-xs break-words whitespace-pre-wrap">
                                        {formatCurrencyBRL(offering.price)}
                                      </p>
                                    </TooltipContent>
                                  </Tooltip>
                                ) : (
                                  <span className="text-muted-foreground/70">
                                    -
                                  </span> // Display hyphen if no price info
                                )}
                              </TableCell>
                              <TableCell className="text-right space-x-1">
                                <Tooltip delayDuration={300}>
                                  <TooltipTrigger asChild>
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => handleEditOffering(index)}
                                    >
                                      <Pencil className="h-4 w-4" />
                                      <span className="sr-only">Editar</span>
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>Editar Oferta</p>
                                  </TooltipContent>
                                </Tooltip>
                                <Tooltip delayDuration={300}>
                                  <TooltipTrigger asChild>
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      className="text-red-600 hover:text-red-700"
                                      onClick={() =>
                                        handleRemoveOffering(index)
                                      }
                                    >
                                      <Trash2 className="h-4 w-4" />
                                      <span className="sr-only">Remover</span>
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>Remover Oferta</p>
                                  </TooltipContent>
                                </Tooltip>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </CardContent>
                </Card>
                {/* Error message specifically for the offerings array */}
                {errors.offering_overview && !errors.offering_overview.root && (
                  <p className="text-xs text-red-600 mt-1">
                    {errors.offering_overview.message ||
                      "Erro na lista de ofertas."}
                  </p>
                )}
                {/* Display root errors for the array if any */}
                {errors.offering_overview?.root && (
                  <p className="text-xs text-red-600 mt-1">
                    {errors.offering_overview.root.message}
                  </p>
                )}
              </div>

              {/* --- Additional Info Fields --- */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="mb-1.5 block" htmlFor="address">
                    Endereço
                  </Label>
                  <Input
                    id="address"
                    placeholder="Rua, Número, Bairro, Cidade, Estado, CEP"
                    {...register("address")}
                  />
                  {errors.address && (
                    <p className="text-xs text-red-600 mt-1">
                      {errors.address.message}
                    </p>
                  )}
                </div>

                <div>
                  <Label className="mb-1.5 block" htmlFor="opening_hours">
                    Horário de Funcionamento (Informativo)
                  </Label>
                  <Input
                    id="opening_hours"
                    placeholder="Ex: Seg-Sex 9h-18h; Sab 9h-12h"
                    {...register("opening_hours")}
                  />
                  {errors.opening_hours && (
                    <p className="text-xs text-red-600 mt-1">
                      {errors.opening_hours.message}
                    </p>
                  )}
                </div>
              </div>
              <div>
                <Label className="mb-1.5 block" htmlFor="fallback_contact_info">
                  Informação de Contato Alternativa
                </Label>
                <Textarea
                  id="fallback_contact_info"
                  rows={2}
                  placeholder="Email ou telefone para onde a IA pode direcionar o cliente se não puder ajudar."
                  {...register("fallback_contact_info")}
                />
                {errors.fallback_contact_info && (
                  <p className="text-xs text-red-600 mt-1">
                    {errors.fallback_contact_info.message}
                  </p>
                )}
              </div>
            </CardContent>
            <CardFooter className="mt-4 flex justify-end border-t pt-6">
              {/* Aviso de alterações não salvas */}
              {isDirty && !isSubmitting && (
                <span className="text-sm text-yellow-600 mr-auto flex items-center">
                  <AlertTriangle className="h-4 w-4 mr-1" />
                  Existem alterações não salvas.
                </span>
              )}
              <Button
                className="ml-auto" // Keep button to the right
                type="submit"
                disabled={formDisabled || !isDirty} // Use the combined disabled state
              >
                {isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Salvar Alterações do Perfil
              </Button>
            </CardFooter>
          </form>
        </fieldset>

        {/* --- Offering Add/Edit Modal --- */}
        <Dialog
          open={isOfferingModalOpen}
          onOpenChange={setIsOfferingModalOpen}
        >
          <DialogContent className="sm:max-w-[800px] max-h-[85vh] flex flex-col">
            <DialogHeader className="flex-shrink-0">
              <DialogTitle>
                {editingOfferingIndex !== null
                  ? "Editar Oferta"
                  : "Adicionar Nova Oferta"}
              </DialogTitle>
            </DialogHeader>
            {/* Render the OfferingForm inside the modal */}
            {/* Pass initial data (if editing) and callbacks */}
            <div className="flex-grow overflow-y-auto mt-4 custom-scrollbar">
              <OfferingForm
                key={editingOfferingIndex ?? "new"}
                initialData={offeringFormData}
                onSubmit={handleSaveOffering}
                onCancel={() => setIsOfferingModalOpen(false)}
                isLoading={isSubmitting}
                isSchedulingFeatureEnabled={isSchedulingEnabled}
              />
            </div>
            {/* Note: Cancel/Save buttons are now part of the OfferingForm component */}
          </DialogContent>
        </Dialog>
      </Card>
    </TooltipProvider>
  );
}
