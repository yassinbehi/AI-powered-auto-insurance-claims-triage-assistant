import { FileX } from "lucide-react";
import Link from "next/link";

import { PageContainer } from "@/components/layout/page-container";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <PageContainer className="max-w-2xl space-y-6">
      <Alert>
        <FileX aria-hidden="true" />
        <AlertTitle>Dossier introuvable</AlertTitle>
        <AlertDescription>
          Aucun sinistre ne porte cet identifiant dans le fichier des déclarations
          que vous avez chargé.
        </AlertDescription>
      </Alert>
      <Button asChild variant="outline">
        <Link href="/">Retour à la file d&apos;attente</Link>
      </Button>
    </PageContainer>
  );
}
