// components/Footer.tsx
import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-background text-muted-foreground border-t border-border py-8">
      <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
        <div className="mb-4 md:mb-0 text-center md:text-left">
          <Link href="/">
            <span className="text-lg text-primary font-semibold ">Lambda Labs</span>
          </Link>
          <p className="text-sm text-gray-500">
            © {new Date().getFullYear()} Lambda Labs. Todos os direitos reservados.
          </p>
        </div>
        {/* <div className="flex space-x-4">
          <Link href="/about">
            <span className="text-sm hover:text-accent-foreground">Sobre</span>
          </Link>
          <Link href="/contact">
            <span className="text-sm  hover:text-accent-foreground">Contato</span>
          </Link>
          <Link href="/privacy">
            <span className="text-sm  hover:text-accent-foreground">Privacidade</span>
          </Link>
        </div> */}
      </div>
    </footer>
  );
}
