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
        <AlertTitle>Analyse introuvable</AlertTitle>
        <AlertDescription>
          Cette analyse n&apos;est plus dans l&apos;historique. Elle a peut-être été
          supprimée depuis.
        </AlertDescription>
      </Alert>
      <Button asChild variant="outline">
        <Link href="/analyses">Retour aux cas analysés</Link>
      </Button>
    </PageContainer>
  );
}
