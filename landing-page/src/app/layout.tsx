import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import Footer from "@/components/ui/home/footer";
import "./globals.css";
import Script from "next/script";


import { Toaster } from "@/components/ui/sonner"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: 'Vendedor IA: Automatize suas vendas 24/7 | Lambda Labs',
  description:
    'Transforme o atendimento do seu negócio com o Vendedor IA da Lambda Labs. Automatize o WhatsApp, qualifique leads e acompanhe as vendas em tempo real.',
  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
  openGraph: {
    title: 'Vendedor IA: Automatize suas vendas 24/7 | Lambda Labs',
    description:
      'Descubra como o Vendedor IA pode aumentar suas vendas automatizando conversas no WhatsApp e otimizando o atendimento ao cliente.',
    url: 'https://www.lambdalabs.com.br/',
    siteName: 'Lambda Labs',
    locale: 'pt_BR',
    type: 'website',
  },
  twitter: {
    title: 'Vendedor IA: Automatize suas vendas 24/7 | Lambda Labs',
    description:
      'Aumente suas conversões com o Vendedor IA. Automatize seu atendimento no WhatsApp e foque no crescimento do seu negócio.',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <Script
          async
          src="https://www.googletagmanager.com/gtag/js?id=AW-16914772618"
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'AW-16914772618');
          `}
        </Script>
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          {children}
          <Footer />
        </ThemeProvider>
        <Toaster position="top-right" />
      </body>
    </html>
  );
}

