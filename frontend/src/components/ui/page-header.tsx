// components/ui/page-header.tsx
import * as React from "react";
import { cn } from "@/lib/utils"; // Assuming you have clsx/tailwind-merge setup

// Main container for the header section
const PageHeader = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => (
    <section
        ref={ref}
        className={cn("flex flex-col gap-2", className)} // Basic flex layout, customize as needed
        {...props}
    >
        {children}
    </section>
));
PageHeader.displayName = "PageHeader";

// Component for the main heading (e.g., H1)
const PageHeaderHeading = React.forwardRef<
    HTMLHeadingElement,
    React.HTMLAttributes<HTMLHeadingElement>
>(({ className, children, ...props }, ref) => (
    <h1
        ref={ref}
        className={cn(
            "text-2xl font-bold leading-tight tracking-tighter md:text-3xl lg:leading-[1.1]", // Example styling
            className
        )}
        {...props}
    >
        {children}
    </h1>
));
PageHeaderHeading.displayName = "PageHeaderHeading";

// Component for the description paragraph
const PageHeaderDescription = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
>(({ className, children, ...props }, ref) => (
    <p
        ref={ref}
        className={cn(
            "max-w-[750px] text-base text-muted-foreground sm:text-lg", // Example styling
            className
        )}
        {...props}
    >
        {children}
    </p>
));
PageHeaderDescription.displayName = "PageHeaderDescription";

export { PageHeader, PageHeaderHeading, PageHeaderDescription };