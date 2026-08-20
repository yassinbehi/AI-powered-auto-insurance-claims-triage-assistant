"use client";

import { ThemeProvider } from "next-themes";
import type * as React from "react";

import { TooltipProvider } from "@/components/ui/tooltip";

/**
 * Le theme sombre est un jeu de tokens (voir globals.css), pas une variante de
 * composant : next-themes ne fait que poser la classe `dark` sur <html>.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
    </ThemeProvider>
  );
}
