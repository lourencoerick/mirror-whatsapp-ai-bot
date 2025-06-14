import { genPageMetadata } from "@/components/seo";
import type { Metadata } from "next";

export const metadata: Metadata = genPageMetadata({
  title: 'Transforme Suas Vendas: Cadastre-se no teste de nosso Vendedor IA',
  description: 'Participe da versão beta do Vendedor IA e experimente a automação de vendas pelo WhatsApp. Cadastre-se e revolucione suas conversões!',
  url: '/beta',
});


export default function BetaSignupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
