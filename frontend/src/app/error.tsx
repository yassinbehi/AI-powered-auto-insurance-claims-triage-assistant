"use client";

import { RefreshCw, Unplug } from "lucide-react";

import { PageContainer } from "@/components/layout/page-container";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

/**
 * La panne la plus frequente en demo est le backend non demarre. Le message
 * l'annonce en clair et donne la commande, au lieu d'afficher une trace.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const backendInjoignable = error.message.includes("injoignable");

  return (
    <PageContainer className="max-w-2xl space-y-6">
      <Alert variant="destructive">
        <Unplug aria-hidden="true" />
        <AlertTitle>
          {backendInjoignable
            ? "L'API de triage est injoignable"
            : "Cette page n'a pas pu être chargée"}
        </AlertTitle>
        <AlertDescription>
          <p>{error.message}</p>
          {backendInjoignable ? (
            <pre className="mt-2 w-full overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs text-foreground">
              uvicorn api:app --app-dir backend/src
            </pre>
          ) : null}
        </AlertDescription>
      </Alert>

      <Button onClick={reset} variant="outline">
        <RefreshCw aria-hidden="true" />
        Réessayer
      </Button>
    </PageContainer>
  );
}
