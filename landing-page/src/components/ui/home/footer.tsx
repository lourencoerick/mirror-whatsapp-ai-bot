// components/Footer.tsx
import SocialIcon from '@/components/ui/blog/social-icons';
import siteMetadata from '@/data/siteMetadata';
import Link from "next/link";

/**
 * The main footer for the website.
 * Contains copyright information, legal links, and social media links.
 * It's designed to be responsive, stacking content on mobile devices.
 */
export default function Footer() {
  return (
    <footer className="bg-background text-muted-foreground border-t border-border mt-auto">
      <div className="container mx-auto px-4 py-8">
        {/* Main flex container for alignment */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">

          {/* Left Side: Copyright and Legal Links */}
          <div className="text-center md:text-left">
            <Link href="/" className="text-lg text-primary font-semibold hover:underline">
              {siteMetadata.headerTitle}
            </Link>
            <p className="text-sm mt-1">
              © {new Date().getFullYear()} {siteMetadata.headerTitle}. Todos os direitos reservados.
            </p>
            {/* Legal links container for better styling */}
            <div className="flex justify-center md:justify-start items-center gap-x-2 mt-2 text-sm">
              <Link href="/politica-de-privacidade" className="text-foreground hover:underline">
                Política de Privacidade
              </Link>
              <span className="text-gray-400">|</span>
              <Link href="/termos-de-servico" className="text-foreground hover:underline">
                Termos de Serviço
              </Link>
            </div>
          </div>

          {/* Right Side: Social Media Icons */}
          <div className="flex flex-wrap justify-center items-center gap-x-4">
            <SocialIcon kind="mail" href={`mailto:${siteMetadata.email}`} size={6} />
            <SocialIcon kind="youtube" href={siteMetadata.youtube} size={6} />
            <SocialIcon kind="linkedin" href={siteMetadata.linkedin} size={6} />
            <SocialIcon kind="instagram" href={siteMetadata.instagram} size={6} />
            {/* Add other social icons as needed */}
          </div>
          
        </div>
      </div>
    </footer>
  );
}