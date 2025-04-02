"use client";

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useAuth } from '@clerk/nextjs';
import { Toaster } from "@/components/ui/sonner";
import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import {
    SidebarInset,
    SidebarProvider,
    SidebarTrigger,
} from "@/components/ui/sidebar";
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch';
import ConversationPanel from "@/components/ui/conversation/conversation-panel";

// --- Step 1: Import Context ---
import { LayoutProvider, useLayoutContext } from '@/contexts/layout-context';

interface UserContextData {
    internal_user_id: string;
    active_account_id: string;
}

interface DashboardLayoutProps {
    children: React.ReactNode;
}

// --- Step 2: Create Inner Component to Access Context ---
const DashboardHeader = () => {
    const { pageTitle } = useLayoutContext();

    return (
        <header className="flex h-16 shrink-0 items-center gap-2 border-b bg-background px-4"> {/* Added px-4, bg, border-b */}
            {/* Sidebar Trigger and Separator */}
            <SidebarTrigger className="-ml-1" />
            <Separator
                orientation="vertical"
                className="mx-2 data-[orientation=vertical]:h-4" // Added margin around separator
            />
            {/* --- Step 3: Replace Breadcrumbs with Dynamic Title --- */}
            <h1 className="text-base font-semibold truncate whitespace-nowrap"> {/* Added truncate/whitespace */}
                {pageTitle}
            </h1>
        </header>
    );
}

// --- Main Layout Component ---
export default function DashboardLayout({
    children
}: DashboardLayoutProps) {
    const pathname = usePathname();
    const isConversationsRoute = pathname.includes('/conversations');

    // --- User Context Fetching Logic ---
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
                    const response = await authenticatedFetch('/api/v1/me');
                    if (!response.ok) {
                        let errorDetail = `Failed to fetch user context: ${response.status}`;
                        try {
                            const errorData = await response.json();
                            errorDetail = errorData.detail || errorDetail;
                        } catch (e) { /* ignore */ }
                        throw new Error(errorDetail);
                    }
                    const data: UserContextData = await response.json();
                    console.log("[DashboardLayout] User context received:", data);
                    setUserContext(data);
                } catch (error: any) {
                    console.error("[DashboardLayout] Error fetching user context:", error);
                    setContextError(error.message || "Failed to load user context");
                    setUserContext(null);
                } finally {
                    setContextLoading(false);
                }
            } else if (isLoaded) {
                console.log("[DashboardLayout] User not signed in.");
                setContextLoading(false);
                setUserContext(null);
                setContextError("User is not signed in.");
            }
        };
        if (isLoaded) { fetchUserContext(); }
    }, [authenticatedFetch, isLoaded, isSignedIn]);

    // --- Loading State (Unchanged) ---
    if (!isLoaded || contextLoading) {
        return (
            <div className="flex items-center justify-center h-screen">
                Carregando...
            </div>
        );
    }

    const socketIdentifier = userContext?.active_account_id;

    return (
        // --- Step 4: Wrap with LayoutProvider ---
        <LayoutProvider>
            <SidebarProvider>
                <AppSidebar />
                {/* Conversation Panel Logic  */}
                {isConversationsRoute && socketIdentifier && <ConversationPanel socketIdentifier={socketIdentifier} />}
                {isConversationsRoute && !socketIdentifier && !contextLoading && contextError && (
                     <div className="w-64 flex-shrink-0 border-r p-4 text-red-500"> Error: {contextError} </div>
                )}

                {/* --- Step 6: Adjust Layout Structure --- */}
                <SidebarInset className="h-screen flex flex-col overflow-hidden"> {/* Use flex-col */}

                    {/* --- Step 5: Render Inner Header --- */}
                    <DashboardHeader />

                    {/* Main Content Area */}
                    {!isSignedIn || contextError ? (
                         <div className="flex-grow flex flex-col items-center justify-center p-4 overflow-auto bg-muted/40"> {/* Added bg, overflow */}
                            Error: {contextError || "Please sign in to continue."}
                         </div>
                    ) : (
                         <main className="flex flex-col flex-1 gap-4 p-4 pt-4  overflow-auto"> {/* Changed div to main, added padding, overflow, bg */}
                            {children}
                            <Toaster richColors position="top-right" />
                         </main>
                    )}

                    {/* Toaster can remain here or move inside <main> if preferred */}
                    
                </SidebarInset>
            </SidebarProvider>
        </LayoutProvider>
    );
}