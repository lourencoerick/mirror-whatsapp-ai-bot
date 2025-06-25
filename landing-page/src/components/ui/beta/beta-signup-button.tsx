"use client";

import { Button } from '@/components/ui/button';
import { trackEvent } from '@/lib/analytics';

import { ArrowRight, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

/**
 * A client component button that redirects users to the beta sign-up page.
 * It handles its own loading state and tracks the conversion event before redirecting.
 */
export function BetaSignupButton() {
  const [isLoading, setIsLoading] = useState(false);

  /**
   * Handles the click event, initiates tracking, and redirects the user.
   */
  const handleClick = () => {
    setIsLoading(true);

    toast.info("Redirecionando para a página de inscrição...");

    const appUrl = process.env.NEXT_PUBLIC_APP_URL;
    if (!appUrl) {
      console.error("A variável de ambiente NEXT_PUBLIC_APP_URL não está definida.");
      toast.error("Erro de configuração", { description: "Não foi possível encontrar a URL de inscrição." });
      setIsLoading(false);
      return;
    }
    
    const signUpUrl = `${appUrl}/sign-up`;
    // This is the callback function that will run after the event is tracked.
    const redirectUser = () => {
      window.location.href = signUpUrl;
    };    

    // Track the conversion and redirect as the callback function.
    trackEvent(
      'signup_click', // 1. A clear, descriptive event name.
      { location: 'main_cta' }, // 2. Contextual parameters for richer data.
      redirectUser, // 3. The callback function to execute after tracking.
      true // 4. The explicit flag indicating this is a Google Ads conversion.
    );
  };

  return (
    <Button 
      size="lg" 
      onClick={handleClick} 
      disabled={isLoading}
      className="font-bold text-lg px-8 py-6"
    >
      {isLoading ? (
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
      ) : (
        <>
          Cadastre-se e Faça sua Inscrição
          <ArrowRight className="ml-2 h-5 w-5" />
        </>
      )}
    </Button>
  );
}