
// components/ui/PhoneMockup.tsx
"use client";

import { cn } from "@/lib/utils"; // Using the utility function from shadcn
import React from "react";

interface PhoneMockupProps {
  /** The content to display inside the phone screen, e.g., an <Image /> component. */
  children: React.ReactNode;
  /** Optional additional class names to apply to the outer frame. */
  className?: string;
}

/**
 * A reusable component that renders a sleek, iPhone-like device mockup frame.
 * It's built with Tailwind CSS and designed to wrap any content.
 * @param {PhoneMockupProps} props The component props.
 * @returns {React.ReactElement} The rendered phone mockup.
 */
const PhoneMockup = ({
  children,
  className,
}: PhoneMockupProps): React.ReactElement => {
  return (
    // The main frame of the device
    <div
      className={cn(
        "relative mx-auto border-gray-800 bg-gray-800 border-[8px] rounded-[2.5rem] h-[550px] w-[270px] shadow-xl",
        className
      )}
    >
      {/* The top notch */}
      <div className="w-[130px] h-[18px] bg-gray-800 top-0 rounded-b-[1rem] left-1/2 -translate-x-1/2 absolute z-10"></div>

      {/* A subtle detail for the side button */}
      <div className="h-[46px] w-[3px] bg-gray-800 absolute -left-[10px] top-[124px] rounded-l-lg"></div>
      <div className="h-[64px] w-[3px] bg-gray-800 absolute -right-[10px] top-[142px] rounded-r-lg"></div>

      {/* The screen area that contains the actual content */}
      <div className="rounded-[2rem] overflow-hidden w-full h-full bg-white">
        {children}
      </div>
    </div>
  );
};

export default PhoneMockup;