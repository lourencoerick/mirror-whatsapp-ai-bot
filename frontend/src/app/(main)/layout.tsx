// app/(main)/layout.tsx
"use client";

import { UserButton, useUser } from "@clerk/nextjs";
import { ReactNode } from "react";

export default function MainGroupLayout({ children }: { children: ReactNode }) {
  const { isSignedIn } = useUser();

  return (
    <div className="relative min-h-screen bg-slate-50">
      {isSignedIn && (
        <div className="absolute top-4 right-4 z-50">
          <UserButton />
        </div>
      )}

      <main className="pt-4 px-4 pb-4 md:pt-4 md:px-6 md:pb-6 lg:pt-4 lg:px-8 lg:pb-8">
        {children}
      </main>
    </div>
  );
}
