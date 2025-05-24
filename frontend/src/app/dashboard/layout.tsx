// app/dashboard/layout.tsx
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { auth, currentUser } from "@clerk/nextjs/server";
import { ReactNode } from "react";
import { ClientDashboardGuard } from "./client-dashboard-guard";
import { DashboardShell } from "./shell";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const user = await currentUser();

  await auth.protect(() => user?.publicMetadata?.role === "admin", {
    unauthorizedUrl: "/pending-approval",
  });

  console.log(`Dashboard admin acessado por ${user?.publicMetadata?.role}`);
  return (
    <SidebarProvider>
      <AppSidebar />
      <DashboardShell>
        <ClientDashboardGuard>{children}</ClientDashboardGuard>
        <Toaster richColors position="top-right" />
      </DashboardShell>
    </SidebarProvider>
  );
}
