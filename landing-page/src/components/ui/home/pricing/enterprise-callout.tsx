"use client";

import { Button } from '@/components/ui/button';
import { ArrowRight } from 'lucide-react';
import React from 'react';

/**
 * A callout component to encourage enterprise clients to get in touch.
 * @returns {React.ReactElement} The rendered callout component.
 */
export function EnterpriseCallout(): React.ReactElement {
  return (
    <div className="mt-12 rounded-lg border  bg-secondary  p-6 text-center">
      <h3 className="text-xl font-semibold text-secondary-foreground">Precisa de mais?</h3>
      <p className="mt-2 text-secondary-foreground">
        Oferecemos soluções personalizadas para grandes equipes e demandas de alta escala com suporte dedicado.
      </p>
      <Button
        asChild
        size="lg"
        className="mt-4 font-semibold"
        // IMPORTANT: Replace with your actual sales email or contact page link
        variant="outline" 
      >
        <a href="mailto:tecnologia@lambdalabs.com.br">
          Falar com Vendas
          <ArrowRight className="ml-2 h-5 w-5" />
        </a>
      </Button>
    </div>
  );
}