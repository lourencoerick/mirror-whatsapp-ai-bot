"use client";

import { useUser, useClerk } from "@clerk/nextjs"; // Import Clerk hooks
import {
  ChevronsUpDown,
  LogOut,
  User as UserIcon,
} from "lucide-react";

import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton"; // Import Skeleton for loading state
import { useRouter } from "next/navigation"; // Import for navigation

/**
 * Component displaying the current user's information and navigation options
 * at the bottom of the sidebar. Fetches user data and sign-out function from Clerk.
 */
export function NavUser() {
  const { isMobile } = useSidebar();
  const { user, isLoaded } = useUser(); // Get user data and loading state
  const { signOut, openUserProfile } = useClerk(); // Get signOut and openUserProfile functions
  const router = useRouter();

  // Handle loading state
  if (!isLoaded) {
    // Show a skeleton loader while user data is being fetched
    return (
      <SidebarMenu>
        <SidebarMenuItem>
           <SidebarMenuButton size="lg" className="cursor-wait">
              <Skeleton className="h-8 w-8 rounded-lg" />
              <div className="grid flex-1 text-left text-sm leading-tight gap-1">
                 <Skeleton className="h-4 w-20 rounded-sm" />
                 <Skeleton className="h-3 w-24 rounded-sm" />
              </div>
           </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }

  // Handle case where user is not signed in (should ideally be handled by layout/middleware)
  if (!user) {
    // Optionally render a sign-in button or null
    // console.warn("[NavUser] User data not available.");
    return null; // Or render a sign-in prompt if appropriate here
  }

  // Prepare user display data
  const userFullName = user.fullName ?? "User";
  const userEmail = user.primaryEmailAddress?.emailAddress ?? "";
  const userImageUrl = user.imageUrl;
  // Generate fallback initials
  const fallbackInitials = `${user.firstName?.charAt(0) ?? ''}${user.lastName?.charAt(0) ?? ''}` || 'U';

  // Handler for signing out
  const handleSignOut = () => {
    signOut(() => router.push('/')); // Redirect to home page after sign out
  };

  // Handler for opening Clerk's User Profile modal
  const handleOpenProfile = () => {
    openUserProfile(); // Opens the modal provided by Clerk
  };

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="h-8 w-8 rounded-lg">
                <AvatarImage src={userImageUrl} alt={userFullName} />
                <AvatarFallback className="rounded-lg">{fallbackInitials}</AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{userFullName}</span>
                <span className="truncate text-xs text-muted-foreground">{userEmail}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="h-8 w-8 rounded-lg">
                  <AvatarImage src={userImageUrl} alt={userFullName} />
                  <AvatarFallback className="rounded-lg">{fallbackInitials}</AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">{userFullName}</span>
                  <span className="truncate text-xs text-muted-foreground">{userEmail}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem onSelect={handleOpenProfile}>
                <UserIcon className="mr-2 h-4 w-4" />
                <span>Account Settings</span>
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={handleSignOut}>
              <LogOut className="mr-2 h-4 w-4" />
              <span>Log out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}