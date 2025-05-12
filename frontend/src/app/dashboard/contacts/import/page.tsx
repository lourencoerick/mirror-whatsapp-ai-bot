"use client";

import ContactImportDialog from "@/components/ui/contact/import/contact-import-dialog"; // Adjust path if needed
import ContactImportJobsTable from "@/components/ui/contact/import/contact-import-jobs-table";
import { useLayoutContext } from "@/contexts/layout-context";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import React, { useEffect } from "react";

const ContactImportPage: React.FC = () => {
  const { setPageTitle } = useLayoutContext();

  // --- Set Page Title ---
  useEffect(() => {
    setPageTitle(
      <div className="flex items-center gap-2">
        <Link
          href="/dashboard/contacts"
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          aria-label="Voltar para Caixas de Entrada"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="font-semibold">Contatos</span>
        </Link>
        <span className="text-sm text-muted-foreground">/</span>
        {"Importar Contatos"}
      </div>
    );
  }, [setPageTitle]);

  return (
    <div className="container mx-auto py-4 px-4 space-y-8">
      <div className="flex flex-row w-full sm:flex-row justify-between items-start sm:items-center gap-4">
        <h2 className="text-xl font-semibold">Histórico de Importações</h2>
        <ContactImportDialog />
      </div>

      <ContactImportJobsTable />
    </div>
  );
};

export default ContactImportPage;
