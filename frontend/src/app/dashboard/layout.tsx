"use client";

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


import ConversationPanel from "./conversation-panel"
import { usePathname } from 'next/navigation'

interface DashboardLayoutProps {
    children: React.ReactNode;
}

export default function DashboardLayout({
    children
}: DashboardLayoutProps) {
    const pathname = usePathname()
    const isConversationsRoute = pathname.includes('/conversations')

    const segments = pathname.split('/').filter(Boolean);

    console.log(pathname, segments)
    // const formattedSegment = segment
    // .replace(/-/g, ' ')
    // .replace(/\b\w/g, (char) => char.toUpperCase());

    return (
        <SidebarProvider>
            <AppSidebar />
            {isConversationsRoute && <ConversationPanel />}
            <SidebarInset>
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
                                        <>
                                            <BreadcrumbItem key={index} className="hidden md:block">
                                                <BreadcrumbLink href={`/${segments.slice(0, index + 1).join('/')}`}>
                                                    {segment.replace(/(^\w{1})|(\s+\w{1})/g, letter => letter.toUpperCase())}
                                                </BreadcrumbLink>
                                            </BreadcrumbItem>
                                            <BreadcrumbSeparator className="hidden md:block" />
                                        </>
                                    ))

                                }
                                <BreadcrumbItem>
                                    <BreadcrumbPage>{segments.at(-1)}</BreadcrumbPage>
                                </BreadcrumbItem>
                            </BreadcrumbList>
                        </Breadcrumb>
                    </div>
                </header>
                <div className="flex flex-col flex-1 gap-4 p-4 pt-0 overflow-none">
                    {children}
                </div>
            </SidebarInset>
        </SidebarProvider>
    )
}
