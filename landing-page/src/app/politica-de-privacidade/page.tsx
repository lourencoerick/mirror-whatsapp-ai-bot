import { genPageMetadata } from "@/components/seo";
import Navbar from "@/components/ui/home/navbar";
import type { Metadata } from "next";

export const metadata: Metadata = genPageMetadata({
  title: "Política de Privacidade – Lambda Labs",
  description:
    "Veja como a Lambda Labs coleta, usa e protege seus dados em nossa plataforma de vendas automatizadas via WhatsApp.",
  url: "/politica-de-privacidade",
});

export default function PoliticaDePrivacidadePage() {
    return (
        <>
        <Navbar hideSignupButton={true} />
      <main className="max-w-3xl mx-auto px-4 py-12 text-foreground">
        
        <h1 className="text-3xl font-bold mb-4">Política de Privacidade – Lambda Labs</h1>
        <p className="text-sm text-gray-500 mb-8">Última atualização: 15 de maio de 2025</p>
  
        <p className="mb-6">
          A <strong>Lambda Labs</strong> está comprometida em proteger a privacidade de seus usuários e clientes.
          Esta Política de Privacidade explica como coletamos, usamos e armazenamos informações ao utilizar nossos
          serviços de automação de vendas via WhatsApp com Inteligência Artificial.
        </p>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">1. Informações que coletamos</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Informações de contato (nome, telefone, e-mail)</li>
            <li>Dados de mensagens enviadas e recebidas via WhatsApp</li>
            <li>Informações de negócios inseridas na plataforma</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">2. Uso das informações</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Executar e aprimorar nossos serviços</li>
            <li>Automatizar interações via WhatsApp</li>
            <li>Gerar relatórios e insights de vendas</li>
            <li>Cumprir obrigações legais</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">3. Compartilhamento de dados</h2>
          <p className="mb-2">Não compartilhamos seus dados com terceiros, exceto:</p>
          <ul className="list-disc pl-6 space-y-1">
            <li>Quando exigido por lei</li>
            <li>Com parceiros técnicos essenciais para o funcionamento da plataforma (ex: provedores de nuvem)</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">4. Segurança</h2>
          <p>
            Adotamos boas práticas de segurança para proteger seus dados contra acesso não autorizado,
            vazamentos ou alterações indevidas.
          </p>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">5. Seus direitos</h2>
          <p>
            Você pode solicitar a atualização, correção ou exclusão de seus dados a qualquer momento, entrando
            em contato conosco.
          </p>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">6. Contato</h2>
          <p>
            Em caso de dúvidas ou solicitações, entre em contato:<br />
            📧 <a href="mailto:tectnologia@lambdalabs.com.br" className="text-blue-600 underline">tectnologia@lambdalabs.com.br</a>
          </p>
        </section>
  
      </main>
      </>
    );
  }
  