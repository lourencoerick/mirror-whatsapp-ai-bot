import { genPageMetadata } from "@/components/seo";
import Navbar from "@/components/ui/home/navbar";
import type { Metadata } from "next";

export const metadata: Metadata = genPageMetadata({
  title: "Política de Privacidade",
  description:
    "Veja como a Lambda Labs coleta, usa e protege seus dados em nossa plataforma de vendas automatizadas via WhatsApp, incluindo integração com Google Calendar.",
  url: "/politica-de-privacidade",
});

export default function PoliticaDePrivacidadePage() {
  return (
    <>
      <Navbar hideSignupButton={true} />
      <main className="max-w-3xl mx-auto px-4 py-12 text-foreground">
        <h1 className="text-3xl font-bold mb-4">
          Política de Privacidade – Lambda Labs
        </h1>
        <p className="text-sm text-gray-500 mb-8">
          Última atualização: 24 de junho de 2025
        </p>

        <p className="mb-6">
          A <strong>Lambda Labs</strong> está comprometida em proteger a
          privacidade de seus usuários e clientes. Esta Política de Privacidade
          explica como coletamos, usamos e armazenamos informações ao utilizar
          nossos serviços de automação de vendas via WhatsApp com Inteligência
          Artificial, incluindo a integração com o Google Calendar.
        </p>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">
            1. Informações que coletamos
          </h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Informações de contato (nome, telefone, e-mail)</li>
            <li>Dados de mensagens enviadas e recebidas via WhatsApp</li>
            <li>Informações de negócios inseridas na plataforma</li>
            <li>
              <strong>Informações do Google Calendar:</strong>
              <ul className="list-disc pl-6 space-y-1">
                <li>Títulos, datas e horários de eventos e compromissos</li>
                <li>Status de disponibilidade (livre/ocupado)</li>
                <li>Escopos autorizados (ex.: calendar.events, calendar.readonly)</li>
                <li>Tokens de acesso e atualização (para manter a integração ativa)</li>
              </ul>
            </li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">2. Uso das informações</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Executar e aprimorar nossos serviços</li>
            <li>Automatizar interações via WhatsApp</li>
            <li>Gerar relatórios e insights de vendas</li>
            <li>
              <strong>Sincronizar e gerenciar compromissos</strong> no seu
              Google Calendar
            </li>
            <li>Cumprir obrigações legais</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">
            3. Compartilhamento de dados
          </h2>
          <p className="mb-2">
            Não compartilhamos seus dados com terceiros, exceto:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>Quando exigido por lei</li>
            <li>
              Com parceiros técnicos essenciais para o funcionamento da
              plataforma (ex: provedores de nuvem)
            </li>
            <li>
              <strong>Com o Google</strong>, estritamente para viabilizar a
              integração com o Google Calendar
            </li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">
            4. Política de Uso de Dados da API do Google
          </h2>
          <p className="mb-2 italic">
            The use of raw or derived user data received from Workspace APIs will adhere to the Google User Data Policy, including the Limited Use requirements.
           <ul className="list-disc pl-6 space-y-1">
            <li>
             <a
                href="https://developers.google.com/workspace/workspace-api-user-data-developer-policy?hl=pt-br"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline hover:text-blue-600"
              >
                Google Workspace User Data and Developer Policy
              </a>
              , including{" "}
              
              <a
                href="https://developers.google.com/workspace/workspace-api-user-data-developer-policy?hl=pt-br#limited-use"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline hover:text-blue-600"
              >
                the Limited Use of user data
              </a> 
              {" "}requirements.
            </li>
            <li>
              Photos API User Data and Developer Policy (for Photos APIs), including{" "}
              <a
                href="https://developers.google.com/photos/support/api-policy#limited_use_of_user_data"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline hover:text-blue-600"
              >
                the Limited Use of user data
              </a> 
              {" "}requirements.
            </li>
          </ul>
   
          </p>
          <p className="mb-4 text-sm">
            (Tradução: O uso de dados crus ou tratados
            recebidas das APIs do Google para qualquer outro aplicativo aderirão
            à Política de Dados do Usuário dos Serviços de API do Google,
            incluindo os requisitos de Uso Limitado.)
          </p>
          <p>
            Especificamente, nossa plataforma acessa os dados do Google Calendar
            com o único propósito de fornecer a funcionalidade de Agendamento
            Automatizado. As informações são usadas exclusivamente para
            encontrar horários disponíveis e gerenciar os agendamentos que você
            autoriza. Estes dados <strong>não são e nunca serão</strong> usados
            para treinar nossos modelos de IA, veicular anúncios ou qualquer
            outro propósito fora da funcionalidade principal da aplicação.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">5. Segurança</h2>
          <p className="mb-2">
            Adotamos boas práticas de segurança para proteger seus dados contra
            acesso não autorizado, vazamentos ou alterações indevidas,
            incluindo:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>Criptografia em trânsito (HTTPS) e em repouso</li>
            <li>Armazenamento seguro de tokens OAuth</li>
            <li>Revisões periódicas de acesso e logs de auditoria</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">6. Seus direitos</h2>
          <p className="mb-2">Você pode solicitar, a qualquer momento:</p>
          <ul className="list-disc pl-6 space-y-1">
            <li>Acesso aos seus dados</li>
            <li>Atualização, correção ou exclusão de informações</li>
            <li>
              Revogação de permissão de acesso ao Google Calendar, tanto pelas
              configurações da sua conta Google quanto entrando em contato
              conosco
            </li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">7. Contato</h2>
          <p>
            Em caso de dúvidas ou solicitações, entre em contato:
            <br />
            📧{" "}
            <a
              href="mailto:tecnologia@lambdalabs.com.br"
              className="text-blue-600 underline"
            >
              tecnologia@lambdalabs.com.br
            </a>
          </p>
        </section>
      </main>
    </>
  );
}