// app/dashboard/layout.tsx
import { ReactNode } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { DashboardShell } from "./shell";
import { auth, currentUser } from "@clerk/nextjs/server";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const user = await currentUser()  

  await auth.protect(
    () => user?.publicMetadata?.role === 'admin',
    {
      unauthorizedUrl:    '/pending-approval',
    }
  );  

  console.log(`Dashboard admin acessado por ${user?.publicMetadata?.role}`);
  return (
    <SidebarProvider>
      <AppSidebar />
      <DashboardShell>{children}</DashboardShell>
    </SidebarProvider>
  );
}
