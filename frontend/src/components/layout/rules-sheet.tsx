"use client";

import { BookOpen } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchRules } from "@/lib/api-client";
import type { RulesDocument } from "@/lib/types";

/**
 * Les documents de reference, a un clic de n'importe quelle page.
 *
 * Ils sont servis tels quels par l'API et affiches sans reformulation : ce
 * sont eux qui font foi, et une paraphrase dans l'interface finirait par
 * diverger du texte que le modele recoit reellement.
 */
export function RulesSheet() {
  const [documents, setDocuments] = React.useState<RulesDocument[] | null>(null);
  const [erreur, setErreur] = React.useState<string | null>(null);
  const [chargement, setChargement] = React.useState(false);

  function chargerSiNecessaire(ouvert: boolean) {
    if (!ouvert || documents || chargement) return;
    setChargement(true);
    setErreur(null);
    fetchRules()
      .then((rules) => setDocuments(rules.documents))
      .catch((e: Error) => setErreur(e.message))
      .finally(() => setChargement(false));
  }

  return (
    <Sheet onOpenChange={chargerSiNecessaire}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm">
          <BookOpen aria-hidden="true" />
          Règles
        </Button>
      </SheetTrigger>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-2xl">
        <SheetHeader className="border-b">
          <SheetTitle>Documents de référence</SheetTitle>
          <SheetDescription>
            Servis tels quels par l&apos;API. En cas d&apos;écart avec l&apos;interface, ce sont
            ces textes qui font foi.
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-8 p-6">
            {chargement ? (
              <div className="space-y-3" aria-busy="true">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-11/12" />
                <Skeleton className="h-4 w-4/5" />
              </div>
            ) : null}

            {erreur ? (
              <p className="text-sm text-destructive">
                Impossible de charger les documents : {erreur}
              </p>
            ) : null}

            {documents?.map((document) => (
              <section key={document.name} className="space-y-3">
                <h3 className="font-mono text-sm font-medium">{document.name}</h3>
                <pre className="overflow-x-auto rounded-md bg-muted p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap">
                  {document.content}
                </pre>
              </section>
            ))}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
