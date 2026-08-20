"use client";

import { ScrollText } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { RulesSheet } from "@/components/layout/rules-sheet";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { cn } from "@/lib/utils";

/**
 * Barre superieure unique. Pas de menu lateral : l'application compte trois
 * routes, et une colonne de navigation permanente couterait de la largeur a
 * un contenu deja dense sans rien orienter de plus.
 */
export function AppHeader() {
  const pathname = usePathname();
  const surFile = pathname === "/";

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-md font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <ScrollText className="size-5 text-muted-foreground" aria-hidden="true" />
          <span>Triage sinistres auto</span>
          <span className="sr-only">— retour à la file d&apos;attente</span>
        </Link>

        <nav className="ml-2 hidden sm:block">
          <Link
            href="/"
            aria-current={surFile ? "page" : undefined}
            className={cn(
              "rounded-md px-2 py-1 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
              // L'etat actif doit se voir sans devenir plus fort que le
              // contenu de la page.
              surFile ? "text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            File d&apos;attente
          </Link>
        </nav>

        <div className="ml-auto flex items-center gap-1">
          <RulesSheet />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
