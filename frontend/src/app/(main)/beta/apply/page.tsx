// src/app/beta/apply/page.tsx
"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { AppBetaStatusEnum, BetaTesterStatusResponse } from "@/lib/enums";
import {
  BetaRequestFormValues,
  betaRequestSchema,
} from "@/lib/validators/beta-request.schema";
import { components } from "@/types/api";
import { useUser } from "@clerk/nextjs";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

type BetaRequestResponse = components["schemas"]["BetaRequestResponse"];

export default function BetaApplicationPage() {
  const { setPageTitle } = useLayoutContext();
  const fetcher = useAuthenticatedFetch();
  const router = useRouter();
  const { isLoaded: isClerkLoaded, isSignedIn } = useUser();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [initialStatusCheckState, setInitialStatusCheckState] = useState<
    "loading" | "show_form" | "redirected"
  >("loading");

  useEffect(() => {
    if (
      isClerkLoaded &&
      fetcher &&
      isSignedIn &&
      initialStatusCheckState === "loading"
    ) {
      const checkExistingApplication = async () => {
        try {
          console.log(
            "BetaApplicationPage: Verificando status de solicitação existente..."
          );
          const response = await fetcher("/api/v1/beta/my-status");

          if (response.ok) {
            const data: BetaTesterStatusResponse = await response.json();
            console.log(
              "BetaApplicationPage: Status recebido da API:",
              data.status
            );
            if (
              data.status === AppBetaStatusEnum.PENDING_APPROVAL ||
              data.status === AppBetaStatusEnum.APPROVED ||
              data.status === AppBetaStatusEnum.DENIED
            ) {
              console.log(
                `BetaApplicationPage: Redirecionando para /beta/status (status: ${data.status})`
              );
              setInitialStatusCheckState("redirected");
              router.replace("/beta/status");
            } else {
              console.log(
                "BetaApplicationPage: Status não requer redirecionamento, mostrando formulário."
              );
              setInitialStatusCheckState("show_form");
            }
          } else if (response.status === 404) {
            console.log(
              "BetaApplicationPage: Nenhuma solicitação beta encontrada (404). Mostrando formulário."
            );
            setInitialStatusCheckState("show_form");
          } else {
            const errorData = await response.json().catch(() => ({}));
            console.error(
              "BetaApplicationPage: Erro ao verificar status beta:",
              response.status,
              errorData.detail
            );
            toast.error("Erro ao Verificar Status", {
              description:
                errorData.detail ||
                "Não foi possível verificar seu status beta no momento.",
            });
            setInitialStatusCheckState("show_form");
          }
        } catch (error) {
          console.error(
            "BetaApplicationPage: Exceção ao verificar status beta:",
            error
          );
          toast.error("Erro Inesperado", {
            description: "Ocorreu um problema ao verificar seu status beta.",
          });
          setInitialStatusCheckState("show_form");
        }
      };
      checkExistingApplication();
    } else if (isClerkLoaded && !isSignedIn) {
      console.log(
        "BetaApplicationPage: Usuário não logado, redirecionando para sign-in."
      );
      setInitialStatusCheckState("redirected");
      router.replace("/sign-in");
    } else if (!isClerkLoaded && initialStatusCheckState === "loading") {
      console.log("BetaApplicationPage: Aguardando Clerk carregar...");
    }
  }, [isClerkLoaded, isSignedIn, fetcher, router, initialStatusCheckState]);

  useEffect(() => {
    if (initialStatusCheckState === "show_form") {
      setPageTitle?.("Inscrição Programa Beta - Lambda Labs");
    }
  }, [setPageTitle, initialStatusCheckState]);

  const form = useForm<BetaRequestFormValues>({
    resolver: zodResolver(betaRequestSchema),
    defaultValues: {
      contact_name: "",
      company_name: "",
      company_website: "",
      business_description: "",
      beta_goal: "",
      has_sales_team: undefined,
      sales_team_size: "",
      avg_leads_per_period: "",
      current_whatsapp_usage: "",
      willing_to_give_feedback: true,
      agree_to_terms: false,
    },
  });

  async function onSubmit(values: BetaRequestFormValues) {
    if (!fetcher) {
      toast.error("Erro de Autenticação", {
        description:
          "Você precisa estar autenticado para enviar a solicitação.",
      });
      return;
    }
    setIsSubmitting(true);

    console.log("Enviando solicitação beta (payload para API):", values);

    try {
      const response = await fetcher("/api/v1/beta/request-access", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(values),
      });
      const responseData: BetaRequestResponse = await response.json();

      if (!response.ok) {
        if (
          response.status === 409 ||
          responseData.message?.toLowerCase().includes("você já solicitou")
        ) {
          toast.info("Solicitação Existente", {
            description:
              responseData.message ||
              "Você já possui uma solicitação em andamento.",
          });
          router.push("/beta/status");
          return;
        }
        throw new Error(
          responseData.message ||
            `Falha ao enviar solicitação: ${response.status} ${response.statusText}`
        );
      }
      toast.success("Solicitação Enviada com Sucesso!", {
        description:
          responseData.message ||
          "Recebemos sua inscrição para o programa beta. Entraremos em contato em breve!",
      });
      router.push("/beta/status");
    } catch (error) {
      console.error("Erro ao enviar solicitação beta:", error);
      const errorMessage =
        error instanceof Error
          ? error.message
          : "Ocorreu um erro desconhecido.";
      toast.error("Falha no Envio", { description: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (initialStatusCheckState === "loading" || !isClerkLoaded) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="mt-4 text-lg text-muted-foreground">
          Verificando seu status...
        </p>
      </div>
    );
  }

  if (initialStatusCheckState === "redirected") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="mt-4 text-lg text-muted-foreground">Redirecionando...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-3xl space-y-8">
        <div className="text-center">
          <h1 className="mt-6 text-4xl font-normal tracking-tight text-gray-900 sm:text-5xl">
            λ
          </h1>
        </div>

        <Card className="bg-white shadow-xl sm:rounded-lg">
          <CardHeader className="px-4 mt-5 sm:px-6  text-center">
            <CardTitle className="text-2xl leading-6 font-bold text-gray-900">
              Formulário de Inscrição Beta
            </CardTitle>
            <CardDescription className="mt-1 text-sm text-gray-500">
              Preencha os campos abaixo para analisarmos sua aplicação.
            </CardDescription>
          </CardHeader>
          <CardContent className="px-4 py-5 sm:p-6">
            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="space-y-6"
              >
                <FormField
                  control={form.control}
                  name="contact_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Seu Nome Completo*</FormLabel>
                      <FormControl>
                        <Input placeholder="Ex: João Silva" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="company_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nome da Empresa</FormLabel>
                      <FormControl>
                        <Input placeholder="Ex: Acme Corp" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="company_website"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Site da Empresa (se houver)</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="https://suaempresa.com"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="business_description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Descreva brevemente seu negócio*</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="O que sua empresa faz e qual seu público principal?"
                          {...field}
                          rows={3}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="beta_goal"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Qual seu principal objetivo ao participar do nosso
                        beta?*
                      </FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Ex: Automatizar respostas, qualificar leads, aumentar vendas..."
                          {...field}
                          rows={3}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="has_sales_team"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center space-x-3 space-y-0 rounded-md border p-3 bg-slate-50">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                          id="has_sales_team"
                        />
                      </FormControl>
                      <div className="space-y-1 leading-none">
                        <FormLabel
                          htmlFor="has_sales_team"
                          className="cursor-pointer"
                        >
                          Possui time de vendas dedicado?
                        </FormLabel>
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {form.watch("has_sales_team") && (
                  <FormField
                    control={form.control}
                    name="sales_team_size"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          Tamanho do time de vendas (aproximado)
                        </FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Selecione..." />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="1-2">1-2 pessoas</SelectItem>
                            <SelectItem value="3-5">3-5 pessoas</SelectItem>
                            <SelectItem value="6-10">6-10 pessoas</SelectItem>
                            <SelectItem value="11-20">11-20 pessoas</SelectItem>
                            <SelectItem value="20+">
                              Mais de 20 pessoas
                            </SelectItem>
                            <SelectItem value="0_not_yet">
                              Ainda não temos, mas planejamos
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
                <FormField
                  control={form.control}
                  name="avg_leads_per_period"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Com quantos leads novos (potenciais clientes) vocês
                        lidam em média?
                      </FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Selecione o volume..." />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="<10/dia">
                            Menos de 10 por dia
                          </SelectItem>
                          <SelectItem value="10-25/dia">
                            10-25 por dia
                          </SelectItem>
                          <SelectItem value="26-50/dia">
                            26-50 por dia
                          </SelectItem>
                          <SelectItem value="51-100/dia">
                            51-100 por dia
                          </SelectItem>
                          <SelectItem value="100+/dia">
                            Mais de 100 por dia
                          </SelectItem>
                          <SelectItem value="varies_greatly">
                            Varia muito / Não sei estimar
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="current_whatsapp_usage"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Como vocês gerenciam o WhatsApp para negócios
                        atualmente?
                      </FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Selecione a forma de uso..." />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="manual_personal_numbers">
                            Manualmente (números pessoais)
                          </SelectItem>
                          <SelectItem value="manual_whatsapp_business">
                            Manualmente (WhatsApp Business App)
                          </SelectItem>
                          <SelectItem value="other_crm_integration">
                            Integrado a um CRM ou outra ferramenta
                          </SelectItem>
                          <SelectItem value="looking_for_solution">
                            Estamos buscando uma solução / Começando agora
                          </SelectItem>
                          <SelectItem value="not_actively_for_sales">
                            Não usamos ativamente para vendas ainda
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="willing_to_give_feedback"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center space-x-3 space-y-0 pt-2">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                          id="willing_to_give_feedback"
                        />
                      </FormControl>
                      <div className="space-y-1 leading-none">
                        <FormLabel
                          htmlFor="willing_to_give_feedback"
                          className="font-normal cursor-pointer text-sm"
                        >
                          Concordo em fornecer feedback regular sobre minha
                          experiência durante o período beta.*
                        </FormLabel>
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="agree_to_terms"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-start space-x-3 border-gray-200">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                          id="agree_to_terms"
                        />
                      </FormControl>
                      <div className="space-y-1 leading-none">
                        <FormLabel
                          htmlFor="agree_to_terms"
                          className="font-normal cursor-pointer text-sm"
                        >
                          Li e concordo com os{" "}
                          <Link
                            href="/beta-terms-of-use.pdf"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-blue-600 hover:text-blue-500 hover:underline"
                          >
                            Termos de Uso do Programa Beta
                          </Link>
                          .*
                        </FormLabel>
                        <FormMessage />
                      </div>
                    </FormItem>
                  )}
                />
                <Button
                  type="submit"
                  className="w-full !mt-10"
                  size="lg"
                  disabled={isSubmitting}
                >
                  {isSubmitting && (
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  )}
                  Quero Transformar Meu WhatsApp!
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
        <p className="text-center text-xs text-gray-500">
          Ao se inscrever, você concorda com nossos Termos de Uso e Política de
          Privacidade. O acesso ao programa beta é limitado e sujeito à
          aprovação.
        </p>
      </div>
    </div>
  );
}
