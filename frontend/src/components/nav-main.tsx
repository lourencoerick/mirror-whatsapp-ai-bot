/* eslint-disable react-hooks/rules-of-hooks */
// src/components/layout/nav-main.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

/**
 * Represents a navigation item in the main navigation.
 * Assumes href is relative to the /dashboard base path (e.g., "/settings").
 */
export interface NavItem {
  title: string;
  href: string;
  icon?: LucideIcon;
  children?: NavItem[];
  exactMatch?: boolean;
}

/**
 * Props for the NavMain component.
 */
interface NavMainProps {
  items: NavItem[];
}

// --- Helper Functions for Active State (Updated for /dashboard context) ---

const DASHBOARD_BASE_PATH = "";

/**
 * Checks if a navigation item is currently active based on the pathname,
 * assuming item hrefs are relative to the /dashboard base path.
 * Considers the `exactMatch` property.
 * @param item - The navigation item to check (e.g., { href: "/settings" }).
 * @param currentPathname - The full current URL pathname (e.g., "/dashboard/settings").
 * @returns True if the item's effective path matches the current pathname.
 */
const isItemActive = (item: NavItem, currentPathname: string): boolean => {
  if (typeof item.href !== 'string') {
    return false;
  }

  // Construct the expected full path within the dashboard
  // Handle href="/" correctly, mapping it to "/dashboard"
  const expectedFullPath = item.href === "/"
    ? DASHBOARD_BASE_PATH
    : `${DASHBOARD_BASE_PATH}${item.href.startsWith('/') ? item.href : '/' + item.href}`; // Ensure leading slash

  if (item.exactMatch) {
    return currentPathname === expectedFullPath;
  }

  // Prefix matching:
  // Handle the base dashboard path itself
  if (expectedFullPath === DASHBOARD_BASE_PATH) {
    // Active if it's exactly "/dashboard" or starts with "/dashboard/"
    // Avoid matching "/dashboard-something-else"
    return currentPathname === DASHBOARD_BASE_PATH || currentPathname.startsWith(DASHBOARD_BASE_PATH + '/');
  }

  // Check for exact match or if the current path starts with the expected full path followed by a '/'
  // Avoid matching partial paths like /dashboard/setting matching /dashboard/settings
  return currentPathname === expectedFullPath || currentPathname.startsWith(expectedFullPath + '/');
};

/**
 * Checks if any child of a navigation item is currently active,
 * assuming child hrefs are relative to the /dashboard base path.
 * Assumes child links typically require an exact match for their full path.
 * @param item - The parent navigation item.
 * @param currentPathname - The full current URL pathname (e.g., "/dashboard/settings/profile").
 * @returns True if at least one child item's effective path is active.
 */
const isAnyChildActive = (item: NavItem, currentPathname: string): boolean => {
  if (!item.children || item.children.length === 0) {
    return false;
  }

  return item.children.some(child => {
    if (typeof child.href !== 'string') {
      return false;
    }
    // Construct the expected full path for the child
    const expectedChildFullPath = child.href === "/"
      ? DASHBOARD_BASE_PATH // Should generally not happen for children, but handle defensively
      : `${DASHBOARD_BASE_PATH}${child.href.startsWith('/') ? child.href : '/' + child.href}`; // Ensure leading slash

    // Children usually require an exact match
    return currentPathname === expectedChildFullPath;
  });
};


// --- Renderer for Individual Items (Internal Component) ---

/**
 * Renders a single navigation item, handling nesting and active states.
 * Manages its own collapsible state if it has children.
 * Skips rendering if the item's href is invalid.
 * @param item - The NavItem data.
 * @param currentPathname - The full current URL pathname.
 */
function NavItemRenderer({ item, currentPathname }: { item: NavItem; currentPathname: string }) {
  // --- Input Validation ---
  if (typeof item.href !== 'string') {
    if (process.env.NODE_ENV === 'development') {
      console.warn(`NavItemRenderer: Skipping item due to invalid href. Title: "${item.title}", Href:`, item.href);
    }
    return null;
  }

  const hasChildren = item.children && item.children.length > 0;
  // Use the updated helper functions
  const isActive = isItemActive(item, currentPathname);
  const isChildActive = isAnyChildActive(item, currentPathname);

  // State for collapsible: open if parent or child is active initially
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const [isOpen, setIsOpen] = React.useState(() => isActive || isChildActive);

  // Effect to potentially update open state if path changes affect active status
  React.useEffect(() => {
    // Use the updated helper functions here too
    const shouldBeOpen = isItemActive(item, currentPathname) || isAnyChildActive(item, currentPathname);
    if (hasChildren && shouldBeOpen && !isOpen) {
        setIsOpen(true);
    }
    // Optional: Close if navigating away and it's no longer active
    // else if (hasChildren && !shouldBeOpen && isOpen) {
    //    setIsOpen(false);
    // }
  }, [currentPathname, item, hasChildren, isOpen]);


  // --- Case 1: Item WITHOUT children ---
  if (!hasChildren) {
    // Construct the full href for the Link component
    const fullHref = item.href === "/"
      ? DASHBOARD_BASE_PATH
      : `${DASHBOARD_BASE_PATH}${item.href.startsWith('/') ? item.href : '/' + item.href}`;

    return (
      <Link
        href={fullHref} // Use the constructed full path for navigation
        className={cn(
          "flex items-center space-x-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          "hover:bg-accent hover:text-accent-foreground",
          isActive
            ? "bg-accent text-accent-foreground font-semibold" // Active state
            : "text-muted-foreground" // Default state
        )}
      >
        {item.icon && <item.icon className="h-4 w-4 flex-shrink-0" aria-hidden="true" />}
        <span className="flex-grow truncate">{item.title}</span>
      </Link>
    );
  }

  // --- Case 2: Item WITH children (Collapsible) ---
  // Construct the full href for the parent Link component
  const parentFullHref = item.href === "/"
    ? DASHBOARD_BASE_PATH
    : `${DASHBOARD_BASE_PATH}${item.href.startsWith('/') ? item.href : '/' + item.href}`;

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="group/collapsible space-y-1"
    >
      {/* Row containing the parent link and the toggle chevron */}
      <div className={cn(
          "flex items-center justify-between rounded-md px-3 py-2",
          "hover:bg-accent", // Hover state for the whole row
          // Highlight row background if parent itself is active (even if collapsed)
          isActive && !isChildActive ? "bg-accent" : ""
        )}
      >
        {/* Link part (Icon + Title) - Navigates */}
        <Link
          href={parentFullHref}
          className={cn(
            "flex flex-1 items-center space-x-3 text-sm font-medium mr-1 transition-colors",
            // Style parent text based on its own active state or if a child is active
            isActive && !isChildActive
              ? "text-primary font-semibold"
              : isChildActive
              ? "text-foreground" 
              : "text-muted-foreground", 
            "group-hover/collapsible:text-accent-foreground" 
          )}
        >
          {item.icon && <item.icon className="h-4 w-4 flex-shrink-0" aria-hidden="true" />}
          <span className="flex-grow truncate">{item.title}</span>
        </Link>

        {/* Chevron Trigger part - Toggles collapse */}
        <CollapsibleTrigger asChild>
          <Button
             variant="ghost"
             size="icon"
             className={cn(
                "h-6 w-6 flex-shrink-0",
                "hover:bg-transparent", 
                "data-[state=open]:text-accent-foreground",
                "data-[state=closed]:text-muted-foreground",
                "group-hover/collapsible:text-accent-foreground"
             )}
             aria-label={`Toggle ${item.title} section`}
          >
            <ChevronRight className="h-4 w-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
          </Button>
        </CollapsibleTrigger>
      </div>

      {/* Collapsible Content (Children) */}
      <CollapsibleContent className="ml-4 space-y-1 border-l border-muted pl-4 py-1">
        {item.children?.map((child) => {
          // --- Child Input Validation ---
          if (typeof child.href !== 'string') {
            if (process.env.NODE_ENV === 'development') {
              console.warn(`NavItemRenderer: Skipping child item due to invalid href. Parent: "${item.title}", Child Title: "${child.title}", Href:`, child.href);
            }
            return null;
          }

          // Construct the full href for the child Link component
          const childFullHref = child.href === "/"
            ? DASHBOARD_BASE_PATH
            : `${DASHBOARD_BASE_PATH}${child.href.startsWith('/') ? child.href : '/' + child.href}`;

          // Use the updated helper function for checking child active state
          const isChildLinkActive = currentPathname === childFullHref;

          return (
            <Link
              key={childFullHref}
              href={childFullHref}
              className={cn(
                "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
                "hover:bg-accent hover:text-accent-foreground",
                isChildLinkActive
                  ? "bg-accent text-accent-foreground font-semibold"
                  : "text-muted-foreground"
              )}
            >
              {child.title}
            </Link>
          );
        })}
      </CollapsibleContent>
    </Collapsible>
  );
}


// --- Main Nav Component ---

/**
 * Renders the main sidebar navigation structure based on the provided items.
 * It iterates through navigation items and uses NavItemRenderer for each.
 * Assumes items have hrefs relative to /dashboard.
 * @param {NavMainProps} props - The component props.
 * @param {NavItem[]} props.items - Array of navigation items to display.
 */
export function NavMain({ items }: NavMainProps) {
  const pathname = usePathname();

  if (!items || items.length === 0) {
    return <nav className="p-2 text-sm text-muted-foreground">No navigation items.</nav>;
  }

  return (
    <nav className="space-y-1 p-2" aria-label="Main Navigation">
      {items.map((item) => (
        <NavItemRenderer key={`${item.title}-${item.href}`} item={item} currentPathname={pathname} />
      ))}
    </nav>
  );
}