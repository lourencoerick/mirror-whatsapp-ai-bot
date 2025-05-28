// app/dashboard/layout.tsx

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { ReactNode } from "react";
import { ClientDashboardGuard } from "./client-dashboard-guard";
import { DashboardShell } from "./shell";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <DashboardShell>
        <ClientDashboardGuard>
          {children}
          <Toaster richColors position="top-right" />
        </ClientDashboardGuard>
      </DashboardShell>
    </SidebarProvider>
  );
}
