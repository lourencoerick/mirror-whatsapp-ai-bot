"use client";

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useAuth } from '@clerk/nextjs';
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch';


import { AppSidebar } from "@/components/app-sidebar"
import {
    Breadcrumb,
    BreadcrumbItem,
    BreadcrumbLink,
    BreadcrumbList,
    BreadcrumbPage,
    BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
    SidebarInset,
    SidebarProvider,
    SidebarTrigger,
} from "@/components/ui/sidebar"


import ConversationPanel from "@/components/ui/conversation/conversation-panel"

interface UserContextData {
    internal_user_id: string;
    active_account_id: string;
}

interface DashboardLayoutProps {
    children: React.ReactNode;
}

export default function DashboardLayout({
    children
}: DashboardLayoutProps) {
    const pathname = usePathname()
    const isConversationsRoute = pathname.includes('/conversations')
    const segments = pathname.split('/').filter(Boolean);

    // --- Add State for User Context ---
    const { isLoaded, isSignedIn } = useAuth();
    const authenticatedFetch = useAuthenticatedFetch();
    const [userContext, setUserContext] = useState<UserContextData | null>(null);
    const [contextError, setContextError] = useState<string | null>(null);
    const [contextLoading, setContextLoading] = useState<boolean>(true); // Start loading

    // --- Add useEffect to Fetch User Context ---
    useEffect(() => {
        const fetchUserContext = async () => {
            // Only fetch if Clerk is loaded and user is signed in
            if (isSignedIn) {
                setContextLoading(true); // Set loading true when starting fetch
                setContextError(null);
                try {
                    console.log("[DashboardLayout] Fetching /api/v1/me...");
                    const response = await authenticatedFetch('/api/v1/me'); // Call /me endpoint
                    if (!response.ok) {
                        let errorDetail = `Failed to fetch user context: ${response.status}`;
                        try {
                            const errorData = await response.json();
                            errorDetail = errorData.detail || errorDetail;
                        } catch (e) { /* ignore json parse error */ }
                        throw new Error(errorDetail);
                    }
                    const data: UserContextData = await response.json();
                    console.log("[DashboardLayout] User context received:", data);
                    setUserContext(data);
                } catch (error: any) {
                    console.error("[DashboardLayout] Error fetching user context:", error);
                    setContextError(error.message || "Failed to load user context");
                    setUserContext(null); // Clear context on error
                } finally {
                    setContextLoading(false); // Set loading false when fetch ends
                }
            } else if (isLoaded) {
                // If Clerk is loaded but user is not signed in
                console.log("[DashboardLayout] User not signed in.");
                setContextLoading(false); // Not loading context
                setUserContext(null);
                setContextError("User is not signed in."); // Optional: set an error state
            }
            // If !isLoaded, do nothing yet, wait for Clerk to load
        };

        // Fetch context only when Clerk is loaded
        if (isLoaded) {
            fetchUserContext();
        }

    }, [authenticatedFetch, isLoaded, isSignedIn]);

    if (!isLoaded || contextLoading) {
        return (
            <div className="flex items-center justify-center h-screen">
                Loading session... {/* Or a spinner/skeleton */}
            </div>
        );
    }


    const socketIdentifier = userContext?.active_account_id;


    return (
        <SidebarProvider>
            <AppSidebar />
            {isConversationsRoute && socketIdentifier && <ConversationPanel socketIdentifier={socketIdentifier}/>}
            {/* Optional: Show error if route matches but ID fetch failed */}
            {isConversationsRoute && !socketIdentifier && !contextLoading && contextError && (
                 <div className="w-64 flex-shrink-0 border-r p-4 text-red-500">
                    Error: {contextError}
                 </div>
            )}            
            <SidebarInset className="h-screen overflow-hidden">
                <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
                    <div className="flex items-center gap-2 px-4">
                        <SidebarTrigger className="-ml-1" />
                        <Separator
                            orientation="vertical"
                            className="mr-2 data-[orientation=vertical]:h-4"
                        />
                        <Breadcrumb>
                            <BreadcrumbList>
                                {
                                    segments.slice(0, -1).map((segment, index) => (
                                        <React.Fragment key={index}>
                                            <BreadcrumbItem className="hidden md:block">
                                                <BreadcrumbLink href={`/${segments.slice(0, index + 1).join('/')}`}>
                                                    {segment.replace(/(^\w{1})|(\s+\w{1})/g, letter => letter.toUpperCase())}
                                                </BreadcrumbLink>
                                            </BreadcrumbItem>
                                            <BreadcrumbSeparator className="hidden md:block" />
                                        </React.Fragment>

                                    ))

                                }
                                <BreadcrumbItem key={segments.length}>
                                    <BreadcrumbPage>{segments.at(-1)}</BreadcrumbPage>
                                </BreadcrumbItem>
                            </BreadcrumbList>
                        </Breadcrumb>
                    </div>
                </header>

                {!isSignedIn || contextError ? (
                    <div className="flex flex-col flex-1 gap-4 p-4 pt-0 overflow-hidden items-center justify-center">
                        Error: {contextError || "Please sign in to continue."}
                    </div>
                ) : (
                    <div className="flex flex-col flex-1 gap-4 p-4 pt-0 overflow-hidden">
                        {children}
                    </div>
                )}
            </SidebarInset>
        </SidebarProvider>
    )
}
