import type { Metadata } from "next";

export const metadata: Metadata = {
    title: 'Transforme Suas Vendas: Cadastre-se na Beta do Vendedor IA | Lambda Labs',
    description:
      'Participe da versão beta do Vendedor IA e experimente a automação de vendas pelo WhatsApp. Cadastre-se e revolucione suas conversões!',
    icons: {
      icon: '/favicon.ico',
      shortcut: '/favicon.ico',
      apple: '/apple-touch-icon.png',
    },
    openGraph: {
      title: 'Transforme Suas Vendas: Cadastre-se na Beta do Vendedor IA | Lambda Labs',
      description:
        'Experimente a nova era das vendas automatizadas com a versão beta do Vendedor IA. Cadastre-se agora e transforme seu atendimento pelo WhatsApp.',
      url: 'https://www.lambdalabs.com.br/beta-signup',
      siteName: 'Lambda Labs',
      locale: 'pt_BR',
      type: 'website',
    },
    twitter: {
      title: 'Transforme Suas Vendas: Cadastre-se na Beta do Vendedor IA | Lambda Labs',
      description:
        'Participe da versão beta do Vendedor IA e automatize suas vendas pelo WhatsApp. Cadastre-se e mude o jogo!',
    },
  };
  
  export default function BetaSignupLayout({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return <>{children}</>;
  }
  