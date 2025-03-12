'use client';
import Image from "next/image";
import Link from "next/link";
import { useForm, ControllerRenderProps } from "react-hook-form";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { TypingAnimation } from "@/components/magicui/typing-animation";
import { InteractiveGridPattern } from "@/components/magicui/interactive-grid-pattern";
import { inter } from '@/components/ui/fonts';
import WhatsAppIcon from '@mui/icons-material/WhatsApp';
import { ArrowLeft } from 'lucide-react';
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import ThemeToggleButton  from "@/components/ui/home/theme-toggle-button"

export const metadata = {
  title: 'Transforme Suas Vendas: Cadastre-se na Beta do Vendedor IA | Lambda Labs',
  description:
    'Experimente a nova era das vendas automatizadas com a versão beta do Vendedor IA. Cadastre-se agora e revolucione seu atendimento pelo WhatsApp.',
  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
  openGraph: {
    title: 'Transforme Suas Vendas: Cadastre-se na Beta do Vendedor IA | Lambda Labs',
    description:
      'Descubra como a versão beta do Vendedor IA pode impulsionar suas vendas automatizando conversas no WhatsApp e otimizando seu atendimento.',
    url: 'https://www.lambdalabs.com.br/beta-signup',
    siteName: 'Lambda Labs',
    locale: 'pt_BR',
    type: 'website',
  },
  twitter: {
    title: 'Transforme Suas Vendas: Cadastre-se na Beta do Vendedor IA | Lambda Labs',
    description:
      'Participe da versão beta do Vendedor IA e descubra como automatizar suas vendas pelo WhatsApp, transformando seu atendimento.',
  },
};


export default function BetaSignupPage() {
  return (
    <main className="bg-background text-foreground shadow-sm md:mt-2">
      <BetaSignupNavbar />

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
          {/* Componente do formulário de inscrição beta */}
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

// Definindo o schema do formulário com Zod
const formSchema = z.object({
  name: z.string().min(1, { message: "Nome é obrigatório." }),
  email: z.string().email({ message: "Digite um email válido." }),
});

type FormData = z.infer<typeof formSchema>;

const BetaSignupForm = () => {
  const router = useRouter();

  function gtag_report_conversion(url?: string) {
    const callback = function () {
      if (url) {
        window.location.href = url;
      }
    };

    if (typeof (window as any).gtag !== "undefined") { // eslint-disable-line @typescript-eslint/no-explicit-any
      (window as any).gtag("event", "conversion", {  // eslint-disable-line @typescript-eslint/no-explicit-any
        send_to: "AW-16914772618/VzaiCJzk26gaEIrly4E_",
        event_callback: callback,
      });  
    }
    return false;
  }

  // Integração do Zod com React Hook Form via zodResolver
  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      email: '',
    }
  });

  async function onSubmit(data: FormData) {
    try {
      const response = await fetch("/api/sheet", { // use sua rota de API
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });
      const result = await response.json();
  
      if (result.result === "success") {
        toast.success("Cadastro realizado com sucesso!");
        router.push('/'); // Redirect to home
      } else {
        toast.error("Ocorreu um erro ao enviar seus dados.");
      }
      form.reset();
    } catch (error) {
      console.error(error);
      toast.error("Erro ao enviar os dados para o Google Sheets.");
    }
  }
  
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 max-w-md mx-auto md:mx-0">
        <FormField
          control={form.control}
          name="name"
          render={({ field }: { field: ControllerRenderProps<FormData, "name"> }) => (
            <FormItem>
              <FormLabel>Nome</FormLabel>
              <FormControl>
                <Input placeholder="Seu nome" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }: { field: ControllerRenderProps<FormData, "email"> }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input placeholder="Seu email" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" onClick={() => gtag_report_conversion()}>Inscrever-se</Button>
      </form>
    </Form>
  );
};

const BetaSignupNavbar = () => {

  return (
    <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="flex justify-between h-16 items-center">
        <Link href="/" className="flex items-center space-x-2">
          <Image
            src="/logo.png"
            alt="Lambda Labs"
            width={100}
            height={30}
            className="w-10 h-auto"
          />
          <div className="h-8 border-l border-muted mx-2" />
          <span className={`${inter.className} text-lg sm:text-2xl font-bold tracking-wide text-foreground`}>
            Lambda Labs
          </span>
        </Link>

        <div className="flex space-x-2 ml-8 items-center">
          <Button asChild variant={"outline"} size={"lg"}>
            <Link href="/" className="text-2xl hover:text-muted-foreground">
              <ArrowLeft className="inline" /><span className="hidden sm:block">Voltar</span>
            </Link>
          </Button>

          <ThemeToggleButton />
           
        </div>
      </div>
    </nav>
  );
};
