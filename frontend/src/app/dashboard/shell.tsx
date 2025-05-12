"use client";

import LoadingLogo from "@/components/loading-logo";
import ConversationPanel from "@/components/ui/conversation/conversation-panel";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { LayoutProvider, useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { useAuth } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import React, { useEffect, useState } from "react";
interface UserContextData {
  internal_user_id: string;
  active_account_id: string;
}

interface DashboardShellProps {
  children: React.ReactNode;
}

const DashboardHeader = () => {
  const { pageTitle } = useLayoutContext();
  return (
    <header className="flex h-20 shrink-0 items-center gap-2 border-b bg-background px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator
        orientation="vertical"
        className="mx-2 data-[orientation=vertical]:h-4"
      />
      <h1 className="text-2xl md:text-3xl tracking-tight font-semibold truncate whitespace-nowrap">
        {pageTitle}
      </h1>
    </header>
  );
};

export function DashboardShell({ children }: DashboardShellProps) {
  const pathname = usePathname();
  const isConversationsRoute = pathname.includes("/conversations");

  const { isLoaded, isSignedIn } = useAuth();
  const authenticatedFetch = useAuthenticatedFetch();
  const [userContext, setUserContext] = useState<UserContextData | null>(null);
  const [contextError, setContextError] = useState<string | null>(null);
  const [contextLoading, setContextLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchUserContext = async () => {
      if (isSignedIn) {
        setContextLoading(true);
        setContextError(null);
        try {
          const response = await authenticatedFetch("/api/v1/me");
          if (!response.ok) {
            let errorDetail = `Failed to fetch user context: ${response.status}`;
            try {
              const errorData = await response.json();
              errorDetail = errorData.detail || errorDetail;
              // eslint-disable-next-line @typescript-eslint/no-unused-vars
            } catch (e) {}
            throw new Error(errorDetail);
          }
          const data: UserContextData = await response.json();
          console.log("[DashboardShell] User context received:", data);
          setUserContext(data);
        } catch (error: unknown) {
          console.error("[DashboardShell] Error fetching user context:", error);
          let errorMsg = "Failed to load user context";
          if (error instanceof Error && error.message) {
            errorMsg = error.message;
          }
          setContextError(errorMsg);
          setUserContext(null);
        } finally {
          setContextLoading(false);
        }
      } else if (isLoaded) {
        console.log("[DashboardShell] User not signed in.");
        setContextLoading(false);
        setUserContext(null);
        setContextError("User is not signed in.");
      }
    };
    if (isLoaded) {
      fetchUserContext();
    }
  }, [authenticatedFetch, isLoaded, isSignedIn]);

  if (!isLoaded || contextLoading) {
    return <LoadingLogo />;
  }

  const socketIdentifier = userContext?.active_account_id;

  return (
    <LayoutProvider>
      {/* Panel lateral condicional */}
      {isConversationsRoute && socketIdentifier && (
        <ConversationPanel socketIdentifier={socketIdentifier} />
      )}
      {isConversationsRoute &&
        !socketIdentifier &&
        !contextLoading &&
        contextError && (
          <div className="w-64 flex-shrink-0 border-r p-4 text-red-500">
            {" "}
            Error: {contextError}{" "}
          </div>
        )}

      <SidebarInset className="h-screen flex flex-col overflow-hidden">
        <DashboardHeader />

        {!isSignedIn || contextError ? (
          <div className="flex-grow flex flex-col items-center justify-center p-4 overflow-auto bg-muted/40">
            Error: {contextError || "Please sign in to continue."}
          </div>
        ) : (
          <main className="flex flex-col flex-1 gap-4 p-4 pt-4 overflow-auto">
            {children}
          </main>
        )}
      </SidebarInset>
    </LayoutProvider>
  );
}
