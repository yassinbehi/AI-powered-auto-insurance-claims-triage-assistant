"use client";

import { RefreshCw, Unplug } from "lucide-react";
import * as React from "react";

import { PageContainer } from "@/components/layout/page-container";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { devWarn } from "@/lib/dev-log";

/**
 * Page d'erreur.
 *
 * Le message d'origine et la commande a lancer sont des informations de
 * developpeur : ils partent dans la console. L'ecran ne dit que ce qu'un
 * gestionnaire peut faire, c'est-a-dire reessayer ou prevenir quelqu'un.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    devWarn(error.message, error.digest);
  }, [error]);

  return (
    <PageContainer className="max-w-2xl space-y-6">
      <Alert variant="destructive">
        <Unplug aria-hidden="true" />
        <AlertTitle>Le service est momentanément indisponible</AlertTitle>
        <AlertDescription>
          Les dossiers ne peuvent pas être chargés pour l&apos;instant. Réessayez dans un
          instant ; si le problème persiste, signalez-le au support.
        </AlertDescription>
      </Alert>

      <Button onClick={reset} variant="outline">
        <RefreshCw aria-hidden="true" />
        Réessayer
      </Button>
    </PageContainer>
  );
}
