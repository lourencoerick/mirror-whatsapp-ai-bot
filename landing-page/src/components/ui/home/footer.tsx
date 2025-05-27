// components/Footer.tsx
import siteMetadata from "@/data/siteMetadata";
import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-background text-muted-foreground border-t border-border py-8 max-h-fit-content mt-auto">
      <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
        <div className="mb-4 md:mb-0 text-center md:text-left">
          <Link href="/">
            <span className="text-lg text-primary font-semibold">
              {siteMetadata.headerTitle}
            </span>
          </Link>
          <p className="text-sm text-gray-500">
            © {new Date().getFullYear()} {siteMetadata.headerTitle}. Todos os direitos reservados.
          </p>

          <div className="flex flex-row gap-1.5">
            
            <p className="text-sm text-gray-500 mt-1">
              <Link
                href="/politica-de-privacidade"
                className="text-foreground hover:underline"
              >
                Política de Privacidade
              </Link>
            </p>

            <p className="text-sm text-gray-500 mt-1">
                | 
            </p> 

            <p className="text-sm text-gray-500 mt-1">
              <Link
                href="/termos-de-servico"
                className="text-foreground hover:underline"
              >
                Termos de Serviço
              </Link>
            </p>               
          </div>
       
        </div>
      </div>
    </footer>
  );
}
