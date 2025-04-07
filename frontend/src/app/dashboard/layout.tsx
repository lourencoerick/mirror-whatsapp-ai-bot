import { ReactNode } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { DashboardShell } from "./shell"

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <DashboardShell>
        {children}
      </DashboardShell>
    </SidebarProvider>
  );
}
