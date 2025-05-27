import { genPageMetadata } from "@/components/seo";
import Navbar from "@/components/ui/home/navbar";
import type { Metadata } from "next";

export const metadata: Metadata = genPageMetadata({
  title: "Termos de Serviço",
  description:
    "Leia os Termos de Serviço da Lambda Labs para uso de nossa plataforma de automação de vendas via WhatsApp.",
  url: "/termos-de-servico",
});

export default function TermosDeServicoPage() {
  return (
    <>
      <Navbar hideSignupButton={true} />
      <main className="max-w-3xl mx-auto px-4 py-12 text-foreground">
        
        <h1 className="text-3xl font-bold mb-4">Termos de Serviço – Lambda Labs</h1>
        <p className="text-sm text-gray-500 mb-8">Última atualização: 26 de maio de 2025</p>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">1. Definições</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li><strong>Serviços</strong>: plataformas web, APIs, apps móveis e demais recursos fornecidos pela Lambda Labs.</li>
            <li><strong>Conteúdo</strong>: quaisquer dados, textos, imagens, vídeos, áudios, marcas, logos e materiais disponibilizados.</li>
            <li><strong>Conta</strong>: registro de Usuário junto à Lambda Labs com credenciais de acesso.</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">2. Elegibilidade</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Usuário deve ter ≥ 18 anos ou autorização legal.</li>
            <li>Informações de cadastro devem ser verdadeiras, precisas e atualizadas.</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">3. Cadastro e Conta</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Para acessar funcionalidades restritas, crie uma Conta.</li>
            <li>Você é responsável pela confidencialidade de sua senha e acesso.</li>
            <li>Notifique imediatamente sobre uso não autorizado ou violação de segurança.</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">4. Licença de Uso</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Licença limitada, não exclusiva, intransferível e revogável para uso interno.</li>
            <li>Proibido sublicenciar, alugar, modificar ou criar trabalhos derivados.</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">5. Obrigações do Usuário</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Usar os Serviços conforme a legislação e bons costumes.</li>
            <li>Não praticar engenharia reversa, envio de spam, malware ou violação de direitos.</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">6. Pagamentos e Tarifas</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Condições, preços e prazos especificados em fatura ou contrato.</li>
            <li>Acesso pode ser suspenso por atraso no pagamento.</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">7. Propriedade Intelectual</h2>
          <p>
            Todos os direitos relacionados aos Serviços e Conteúdos pertencem à Lambda Labs ou a licenciadores.
            Nenhum direito é transferido ao Usuário além da licença expressa nestes Termos.
          </p>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">8. Modificação dos Serviços e Termos</h2>
          <p>
            Podemos alterar, suspender ou descontinuar os Serviços ou estes Termos a qualquer momento.
            O uso continuado após mudanças implica aceitação.
          </p>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">9. Isenção de Garantias</h2>
          <p>
            Os Serviços são fornecidos “no estado em que se encontram” e “conforme disponíveis”, sem garantias de qualquer tipo.
          </p>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">10. Limitação de Responsabilidade</h2>
          <p>
            Na máxima extensão permitida por lei, não seremos responsáveis por danos indiretos, incidentais ou consequenciais.
            Nossa responsabilidade total não excederá o valor pago nos últimos três meses.
          </p>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">11. Privacidade</h2>
          <p>
            O tratamento de seus dados pessoais ocorre conforme nossa <a href="/politica-de-privacidade" className="text-blue-600 underline">Política de Privacidade</a>.
          </p>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">12. Rescisão</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Usuário pode encerrar a Conta a qualquer momento.</li>
            <li>Podemos suspender ou encerrar acesso por violação destes Termos.</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">13. Disposições Gerais</h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Estes Termos são o acordo integral entre as partes.</li>
            <li>Se qualquer cláusula for inválida, as demais permanecem em vigor.</li>
            <li>Regidos pela lei do Estado de São Paulo, foro Central da Comarca de São Paulo.</li>
          </ul>
        </section>
  
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-2">14. Contato</h2>
          <p>
            Para dúvidas ou suporte, entre em contato:<br />
            📧 <a href="mailto:tecnologia@lambdalabs.com.br" className="text-blue-600 underline">tecnologia@lambdalabs.com.br</a><br />
          </p>
        </section>
  
      </main>
    </>
  );
}
