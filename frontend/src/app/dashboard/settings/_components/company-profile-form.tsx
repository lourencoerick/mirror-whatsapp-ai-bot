// app/dashboard/settings/_components/CompanyProfileForm.tsx
"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FetchFunction } from "@/hooks/use-authenticated-fetch"; // Hook de fetch
import { updateCompanyProfile } from "@/lib/api/company-profile"; // Função da API
import {
  CompanyProfileFormData,
  companyProfileValidationSchema,
} from "@/lib/validators/company-profile.schema"; // Schema Zod
import { components } from "@/types/api"; // Tipos gerados pela API
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";

import { StringListInput } from "@/components/custom/single-list-input";
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
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Pencil, PlusCircle, Trash2 } from "lucide-react";
import { toast } from "sonner"; // IMPORTAR toast do sonner

import { OfferingForm } from "./offering-form";
// Tipos para props
type CompanyProfileSchemaOutput =
  components["schemas"]["CompanyProfileSchema-Output"];
type OfferingInfo = components["schemas"]["OfferingInfo"];

interface CompanyProfileFormProps {
  initialData: CompanyProfileSchemaOutput | null; // Dados iniciais para preencher
  fetcher: FetchFunction; // Passar a função fetch autenticada
  onProfileUpdate: (updatedProfile: CompanyProfileSchemaOutput) => void; // Callback após salvar
}

export function CompanyProfileForm({
  initialData,
  fetcher,
  onProfileUpdate,
}: CompanyProfileFormProps) {
  const form = useForm<CompanyProfileFormData>({
    resolver: zodResolver(companyProfileValidationSchema),
    defaultValues: {
      // Pré-popular o formulário
      company_name: initialData?.company_name || "",
      website: initialData?.website || "",
      address: initialData?.address || "",
      business_description: initialData?.business_description || "",
      target_audience: initialData?.target_audience || "",
      sales_tone:
        initialData?.sales_tone || "friendly, helpful, and professional",
      language: initialData?.language || "pt-BR",
      communication_guidelines: initialData?.communication_guidelines || [],
      ai_objective:
        initialData?.ai_objective ||
        "Engage customers, answer questions about offerings, and guide them towards a purchase or next step.",
      key_selling_points: initialData?.key_selling_points || [],
      delivery_options: initialData?.delivery_options || [],
      opening_hours: initialData?.opening_hours || "",
      fallback_contact_info: initialData?.fallback_contact_info || "",
      // Não incluir ID ou profile_version no formulário editável
    },
  });

  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = form;

  // --- Gerenciamento de Estado para Offerings ---
  // Usar useFieldArray para gerenciar a lista de offerings dentro do react-hook-form
  const {
    fields: offerings,
    append,
    remove,
    update,
  } = useFieldArray({
    control,
    name: "offering_overview", // Nome do campo no schema Zod/FormData
    // keyName: "customId" // Opcional: Usar um ID diferente de 'id' para React keys
  });

  // Estado para controlar o modal/dialog de edição/criação
  const [isOfferingModalOpen, setIsOfferingModalOpen] = useState(false);
  const [editingOfferingIndex, setEditingOfferingIndex] = useState<
    number | null
  >(null); // Índice da oferta sendo editada
  const [offeringFormData, setOfferingFormData] = useState<OfferingInfo | null>(
    null
  ); // Dados para pré-popular form de edição

  // Resetar formulário se os dados iniciais mudarem (ex: após pesquisa)
  useEffect(() => {
    if (initialData) {
      reset({
        company_name: initialData.company_name || "",
        website: initialData.website || "",
        address: initialData.address || "",
        business_description: initialData.business_description || "",
        target_audience: initialData.target_audience || "",
        sales_tone:
          initialData.sales_tone || "friendly, helpful, and professional",
        language: initialData.language || "pt-BR",
        communication_guidelines: initialData.communication_guidelines || [],
        ai_objective:
          initialData.ai_objective ||
          "Engage customers, answer questions about offerings, and guide them towards a purchase or next step.",
        key_selling_points: initialData.key_selling_points || [],
        delivery_options: initialData.delivery_options || [],
        offering_overview: initialData.offering_overview || [],
        opening_hours: initialData.opening_hours || "",
        fallback_contact_info: initialData.fallback_contact_info || "",
      });
    }
  }, [initialData, reset]);

  const handleAddNewOffering = () => {
    setEditingOfferingIndex(null); // Indica que é uma nova oferta
    setOfferingFormData(null); // Limpa dados iniciais do form
    setIsOfferingModalOpen(true);
  };

  const handleEditOffering = (index: number) => {
    setEditingOfferingIndex(index);
    setOfferingFormData(offerings[index] as OfferingInfo); // Pega dados da oferta clicada
    setIsOfferingModalOpen(true);
  };

  const handleRemoveOffering = (index: number) => {
    remove(index); // Remove do array do react-hook-form
    toast.info("Offering removed.");
  };

  // Callback para quando o OfferingForm for salvo (dentro do modal)
  const handleSaveOffering = (data: OfferingInfo) => {
    const dataToSave = {
      ...data,
      key_features: data.key_features || [], // Se for undefined/null, usa array vazio
    };

    if (editingOfferingIndex !== null) {
      // Atualizar existente
      update(editingOfferingIndex, dataToSave);
      toast.success("Offering updated.");
    } else {
      // Adicionar novo
      append(dataToSave);
      toast.success("Offering added.");
    }
    setIsOfferingModalOpen(false); // Fechar modal
    setEditingOfferingIndex(null);
    setOfferingFormData(null);
  };

  const onSubmit = async (formData: CompanyProfileFormData) => {
    console.log("Form data submitted:", formData);
    try {
      // Prepara o payload completo (incluindo campos não editáveis se necessário pela API PUT)
      // O schema Pydantic no backend deve lidar com campos faltantes/opcionais
      const payload: CompanyProfileSchemaOutput = {
        ...(initialData || {}), // Inclui dados existentes como ID, version, etc.
        ...formData, // Sobrescreve com dados do formulário
        // Garante que campos de array vazios sejam enviados como [] e não undefined
        communication_guidelines: formData.communication_guidelines || [],
        key_selling_points: formData.key_selling_points || [],
        delivery_options: formData.delivery_options || [],
        profile_version: initialData?.profile_version || 1, // Manter versão existente
        // id: initialData?.id, // Passar ID se existir para PUT
        // account_id: initialData?.account_id, // Passar account_id se existir
        // created_at: initialData?.created_at, // Passar timestamps se existirem
        // updated_at: initialData?.updated_at,
      };

      payload.offering_overview = formData.offering_overview || [];

      const updatedProfile = await updateCompanyProfile(fetcher, payload);

      if (updatedProfile) {
        toast.success("Success!", {
          // Usar toast.success ou similar
          description: "Company profile updated successfully.",
        });
        onProfileUpdate(updatedProfile); // Chama o callback para atualizar o estado na página pai
      } else {
        // A função da API deve lançar erro, mas por segurança:
        throw new Error("Update function returned null unexpectedly.");
      }
    } catch (error: any) {
      console.error("Failed to update profile:", error);
      toast.error("Error updating profile", {
        // Usar toast.error ou similar
        description: error.message || "An unexpected error occurred.",
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Company Profile Details</CardTitle>
        <CardDescription>
          Edit the core information about your company. This data is used by the
          AI Seller.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="space-y-4">
          {/* --- Campos Simples --- */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="mb-1.5 block" htmlFor="company_name">
                Company Name
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
                Website URL
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
              Business Description
            </Label>
            <Textarea
              id="business_description"
              rows={4}
              {...register("business_description")}
            />
            {errors.business_description && (
              <p className="text-xs text-red-600 mt-1">
                {errors.business_description.message}
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="mb-1.5 block" htmlFor="sales_tone">
                AI Sales Tone
              </Label>
              <Input
                id="sales_tone"
                placeholder="e.g., friendly, professional"
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
                Primary Language
              </Label>
              {/* TODO: Replace with Shadcn Select component */}
              <Input
                id="language"
                placeholder="e.g., pt-BR"
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
              AI Objective
            </Label>
            <Textarea
              id="ai_objective"
              rows={3}
              {...register("ai_objective")}
            />
            {errors.ai_objective && (
              <p className="text-xs text-red-600 mt-1">
                {errors.ai_objective.message}
              </p>
            )}
          </div>

          <div>
            <Controller
              name="communication_guidelines" // Nome do campo no schema/form data
              control={control} // Passar o controle do useForm
              render={(
                { field, fieldState: { error } } // Render prop fornece field e error
              ) => (
                <StringListInput
                  field={field} // Passar o objeto field para o componente
                  label="Communication Guidelines (DOs/DON'Ts)"
                  id="communication_guidelines"
                  placeholder="Add a guideline..."
                  error={error} // Passar o erro específico deste campo
                />
              )}
            />
          </div>

          <div>
            <Controller
              name="key_selling_points"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <StringListInput
                  field={field}
                  label="Key Selling Points (USPs)"
                  id="key_selling_points"
                  placeholder="Add a selling point..."
                  error={error}
                />
              )}
            />
          </div>

          <div>
            <Controller
              name="delivery_options"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <StringListInput
                  field={field}
                  label="Delivery/Pickup Options"
                  id="delivery_options"
                  placeholder="Add an option..."
                  error={error}
                />
              )}
            />
          </div>

          {/* Renderizar usando Tabela + Modal/Sheet */}
          <div className="space-y-2">
            <Label className="mb-1.5 block">
              Offerings (Products/Services/Plans)
            </Label>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">
                  Current Offerings
                </CardTitle>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleAddNewOffering}
                >
                  <PlusCircle className="mr-2 h-4 w-4" /> Add Offering
                </Button>
              </CardHeader>
              <CardContent>
                {offerings.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic text-center py-4">
                    No offerings added yet.
                  </p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead className="hidden md:table-cell">
                          Description
                        </TableHead>
                        <TableHead>Price Info</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {offerings.map((offering, index) => (
                        <TableRow key={offering.id}>
                          {" "}
                          {/* Use offering.id gerado por useFieldArray */}
                          <TableCell className="font-medium">
                            {offering.name}
                          </TableCell>
                          <TableCell className="hidden md:table-cell text-sm text-muted-foreground truncate max-w-xs">
                            {offering.short_description}
                          </TableCell>
                          <TableCell>{offering.price_info || "-"}</TableCell>
                          <TableCell className="text-right space-x-1">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => handleEditOffering(index)}
                            >
                              <Pencil className="h-4 w-4" />
                              <span className="sr-only">Edit</span>
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="text-red-600 hover:text-red-700"
                              onClick={() => handleRemoveOffering(index)}
                            >
                              <Trash2 className="h-4 w-4" />
                              <span className="sr-only">Remove</span>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
            {/* Registrar o campo array para que RHF o inclua na submissão, mesmo que não tenha um input direto aqui */}
            {/* <input type="hidden" {...register("offering_overview")} /> */}
            {/* Alternativamente, o useFieldArray já faz o registro */}
            {errors.offering_overview && (
              <p className="text-xs text-red-600 mt-1">
                {errors.offering_overview.message || "Error in offerings list."}
              </p>
            )}
          </div>

          {/* --- Outros Campos --- */}
          <div>
            <Label className="mb-1.5 block" htmlFor="address">
              Address
            </Label>
            <Input id="address" {...register("address")} />
            {errors.address && (
              <p className="text-xs text-red-600 mt-1">
                {errors.address.message}
              </p>
            )}
          </div>
          <div>
            <Label className="mb-1.5 block" htmlFor="opening_hours">
              Opening Hours
            </Label>
            <Input
              id="opening_hours"
              placeholder="e.g., Mon-Fri 9am-5pm PST"
              {...register("opening_hours")}
            />
            {errors.opening_hours && (
              <p className="text-xs text-red-600 mt-1">
                {errors.opening_hours.message}
              </p>
            )}
          </div>
          <div>
            <Label className="mb-1.5 block" htmlFor="fallback_contact_info">
              Fallback Contact Info
            </Label>
            <Textarea
              id="fallback_contact_info"
              rows={2}
              {...register("fallback_contact_info")}
            />
            {errors.fallback_contact_info && (
              <p className="text-xs text-red-600 mt-1">
                {errors.fallback_contact_info.message}
              </p>
            )}
          </div>
        </CardContent>
        <CardFooter className="flex justify-end">
          <Button
            className="mt-4 ml-auto block"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Profile Changes
          </Button>
        </CardFooter>
      </form>
      {/* --- Modal/Dialog para Adicionar/Editar Oferta --- */}
      <Dialog open={isOfferingModalOpen} onOpenChange={setIsOfferingModalOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>
              {editingOfferingIndex !== null
                ? "Edit Offering"
                : "Add New Offering"}
            </DialogTitle>
          </DialogHeader>
          {/* Renderiza o formulário de oferta dentro do modal */}
          {/* Passa os dados iniciais (se editando) e os callbacks */}
          <OfferingForm
            key={editingOfferingIndex ?? "new"} // Força re-render com dados corretos
            initialData={offeringFormData}
            onSubmit={handleSaveOffering}
            onCancel={() => setIsOfferingModalOpen(false)}
            isLoading={isSubmitting} // Passar estado de loading principal? Ou gerenciar separado?
          />
          {/* Os botões Cancel/Save estão dentro do OfferingForm agora */}
          {/* <DialogFooter>
                  <Button type="button" variant="secondary" onClick={() => setIsOfferingModalOpen(false)}>Cancel</Button>
                  <Button type="submit" form="offering-form-id">Save Offering</Button> // Se botões ficassem aqui
              </DialogFooter> */}
        </DialogContent>
      </Dialog>
    </Card>
  );
}
