"use client";

import { NavUser } from "@/components/nav-user";
import { NavAccount } from "@/components/nav-account";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { UserCheck } from "lucide-react"; // Example icon

// --- Configuration Import ---
import { sidebarNavItems } from "@/config/sidebar-nav";
import type { NavItem as ConfigNavItem } from "@/config/sidebar-nav"; 
import { NavMain, type NavItem as NavMainItem } from "@/components/nav-main";

// --- Placeholder Data  ---
// TODO: use the account route to get the data from backend
// or use org hook from clerk
const accountData = {
  name: "Conta Individual", 
  logo: UserCheck,
  plan: "Plano PME",
};

// --- Helper Function for Data Mapping ---
/**
 * Maps the NavItem structure from config to the structure expected by NavMain.
 * @param {ConfigNavItem} navItem - The navigation item from the config.
 * @returns {NavMainItem} An object suitable for the NavMain component's 'items' prop.
 */
const mapNavItemToNavMainProps = (navItem: ConfigNavItem): NavMainItem => {
  // Ensure the output matches NavMainItem: { title: string, href: string, ... }
  const mappedItem: NavMainItem = {
    title: navItem.name,
    href: navItem.href,
    icon: navItem.icon,
    children: navItem.children
      ?.filter((child) => !child.hidden)
      .map(mapNavItemToNavMainProps),
    exactMatch: navItem.exactMatch,
  };
  return mappedItem;
};


/**
 * The main application sidebar component.
 */
export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  // console.log("Raw sidebarNavItems:", JSON.stringify(sidebarNavItems, null, 2));

  // Filter out hidden items
  const visibleNavItems = sidebarNavItems.filter(
    (item) => !item.hidden
  );

  

  // console.log("Visible Nav Items:", JSON.stringify(visibleNavItems, null, 2));

  const navMainPropsItems = visibleNavItems.map(mapNavItemToNavMainProps);

  // console.log("Items passed to NavMain:", JSON.stringify(navMainPropsItems, null, 2));

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <NavAccount account={accountData} />
      </SidebarHeader>

      <SidebarContent>
        <NavMain items={navMainPropsItems} />
      </SidebarContent>

      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
    </Sidebar>
  );
}