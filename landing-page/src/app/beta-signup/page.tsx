/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';


import { useState } from 'react';
import { useRouter } from "next/navigation";

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { TypingAnimation } from "@/components/magicui/typing-animation";
import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";
import Navbar from "@/components/ui/home/navbar";

import WhatsAppIcon from '@mui/icons-material/WhatsApp';
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useForm } from "react-hook-form";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";


// Main Page Component (No changes needed here for this step)
export default function BetaSignupPage() {
  return (
    <main className="bg-background text-foreground shadow-sm md:mt-2">
      <Navbar hideSignupButton={true} />

      <div className="container mx-auto px-4 flex flex-col md:flex-row items-center py-10">
        <div className="w-full md:w-7/10 text-center md:text-left">
          <TypingAnimation
            duration={60}
            className="text-4xl md:text-5xl font-normal mt-0 mb-4 typing-container"
            as="h1"
            style={{ whiteSpace: "pre-line" }}
          >
            Seja um dos primeiros a transformar seu WhatsApp em uma máquina de vendas
          </TypingAnimation>
          <p className="text-xl md:text-2xl mb-8 leading-relaxed">
            Lambda Labs está <span className="font-bold">oferecendo acesso antecipado</span> para empresas selecionadas.<br />
            Inscreva-se para concorrer à <span className="font-bold">oportunidade de testar gratuitamente</span> nossa Inteligência Artificial que <span className="font-bold">automatiza suas vendas pelo </span>WhatsApp <WhatsAppIcon />.
          </p>
          {/* Beta Signup Form Component */}
          <div className="mt-8">
            <BetaSignupForm />
          </div>
        </div>

        <div className="w-full md:w-3/10 mt-8 md:mt-0 flex justify-center relative hidden md:flex">
          <div className="relative z-10 w-full aspect-[12/16] lambda-shape">
            <InteractiveGridPattern />
          </div>
        </div>
      </div>
    </main>
  );
}


// Zod schema definition
const formSchema = z.object({
  name: z.string().min(1, { message: "Nome é obrigatório." }),
  email: z.string().email({ message: "Digite um email válido." }),
});

// Type inferred from the schema
type FormData = z.infer<typeof formSchema>;

/**
 * Renders the beta signup form and handles submission with loading state.
 * @returns {JSX.Element} The beta signup form component.
 */
const BetaSignupForm = () => {
  const router = useRouter();
  // State to manage the loading status of the form submission
  const [isLoading, setIsLoading] = useState(false);

  async function hashSHA256(value: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(value.trim().toLowerCase());
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(hashBuffer))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  function gtag_report_conversion(url?: string) {
    const callback = function () {
      if (url) {
        window.location.href = url;
      }
    };

    if (typeof (window as any).gtag === "function") {
      (window as any).gtag("event", "conversion", {
        send_to: "AW-16914772618/VzaiCJzk26gaEIrly4E_",
        event_callback: callback,
      });
    } else {
      console.warn("gtag function not found on window object.");

      callback();
    }
    return false;
  }


  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      email: '',
    }
  });

  /**
   * Handles form submission: sends data to the API, shows feedback, and manages loading state.
   * @param {FormData} data - The validated form data.
   */
  async function onSubmit(data: FormData) {
    setIsLoading(true);
    try {
      const response = await fetch("/api/sheet", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });


      if (!response.ok) {

        let errorMsg = "Ocorreu um erro ao enviar seus dados.";
        try {
          const errorResult = await response.json();
          errorMsg = errorResult.detail || errorMsg;
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
        } catch (parseError) {
          // Ignore if response body is not JSON or empty
        }
        throw new Error(errorMsg);
      }

      const result = await response.json();

      // Assuming backend returns { result: "success" } on success
      if (result.result === "success") {

        const hashedEmail = await hashSHA256(data.email);
        const hashedName = await hashSHA256(data.name);


        if (typeof window !== "undefined" && typeof (window as any).gtag === "function") {
          (window as any).gtag('set', 'user_data', {
            email: hashedEmail,
            first_name: hashedName,
          });
        }

        toast.success("Cadastro realizado com sucesso!");
        gtag_report_conversion();
        form.reset();
        router.push('/');
      } else {

        toast.error(result.message || "Falha no cadastro. Tente novamente.");
      }
    } catch (error) {
      console.error("Submission error:", error);

      toast.error(error instanceof Error ? error.message : "Erro ao conectar com o servidor.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Form {...form}>
      {/* Use react-hook-form's handleSubmit to trigger validation and our onSubmit */}
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 max-w-md mx-auto md:mx-0">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nome</FormLabel>
              <FormControl>
                {/* Optionally disable input during loading */}
                <Input placeholder="Seu nome" {...field} disabled={isLoading} />
              </FormControl>
              <FormMessage /> {/* Shows validation errors */}
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                {/* Optionally disable input during loading */}
                <Input placeholder="Seu email" type="email" {...field} disabled={isLoading} />
              </FormControl>
              <FormMessage /> {/* Shows validation errors */}
            </FormItem>
          )}
        />
        {/* Submit Button: Disabled state and loading indicator */}
        <Button type="submit" disabled={isLoading} className="w-full md:w-auto">
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Enviando...
            </>
          ) : (
            'Inscrever-se'
          )}
        </Button>
      </form>
    </Form>
  );
};