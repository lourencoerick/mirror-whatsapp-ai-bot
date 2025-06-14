"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import { Button } from '@/components/ui/button';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';

import { setGoogleAnalyticsUserData, trackGoogleAdsConversion } from "@/lib/analytics";
import { submitBetaUser } from "@/lib/api/beta";

const formSchema = z.object({
  name: z.string().min(1, { message: "Nome é obrigatório." }),
  email: z.string().email({ message: "Digite um email válido." }),
});

type FormData = z.infer<typeof formSchema>;

/**
 * Renders the beta signup form and orchestrates the submission process.
 * This form captures lead data and then redirects the user to the final app registration page.
 */
export function BetaSignupForm() {
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: '', email: '' }
  });

  /**
   * Orchestrates the lead capture and redirection flow.
   */
  async function onSubmit(data: FormData) {
    setIsLoading(true);
    try {
      // Step 1: Submit the lead data to our backend (e.g., Google Sheets).
      await submitBetaUser(data);

      // Step 2: Set user data for analytics.
      await setGoogleAnalyticsUserData(data);

      // Step 3: Prepare the redirect URL to the main app's sign-up page.
      const appUrl = process.env.NEXT_PUBLIC_APP_URL;
      if (!appUrl) {
          console.error("A variável de ambiente NEXT_PUBLIC_APP_URL não está definida.");
          throw new Error("Erro de configuração interna. Tente novamente mais tarde.");
      }
      
      // UX Improvement: Pass the email as a query parameter to pre-fill the next form.
      const signUpUrl = `${appUrl}/sign-up?email=${encodeURIComponent(data.email)}`;
      
      // Step 4: Notify the user they are being redirected.
      toast.success("Inscrição recebida!", {
        description: "Agora vamos finalizar seu cadastro na nossa plataforma.",
      });
      
      // Step 5: Track the conversion and use the redirect as the callback.
      // This ensures the tracking pixel has the best chance to fire before the page changes.
      trackGoogleAdsConversion(() => {
        window.location.href = signUpUrl;
      });
      
      form.reset();

    } catch (error) {
      console.error("Submission error:", error);
      toast.error("Falha na Inscrição", {
        description: error instanceof Error ? error.message : "Por favor, tente novamente mais tarde.",
      });
      setIsLoading(false); // Only reset loading on error, as success will navigate away.
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 max-w-md mx-auto md:mx-0">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nome</FormLabel>
              <FormControl>
                <Input placeholder="Seu nome" {...field} disabled={isLoading} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email de trabalho</FormLabel>
              <FormControl>
                <Input placeholder="seu@email.com" type="email" {...field} disabled={isLoading} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={isLoading} className="w-full md:w-auto">
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Aguarde...
            </>
          ) : (
            'Quero meu acesso antecipado'
          )}
        </Button>
      </form>
    </Form>
  );
};