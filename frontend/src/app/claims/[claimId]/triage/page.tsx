import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/layout/page-container";
import { TypeSinistreBadge } from "@/components/status/domain-badges";
import { TriageRunView } from "@/components/triage/triage-run-view";
import { Button } from "@/components/ui/button";
import { ApiNotFoundError, fetchClaimDetail } from "@/lib/api-server";

/**
 * Page de triage. Le contexte du dossier est rendu cote serveur (gratuit) ;
 * seul le deroule du triage est un composant client, parce qu'il consomme un
 * flux SSE.
 */
// Voir la note de src/app/page.tsx : rendu a chaque requete.
export const dynamic = "force-dynamic";

export default async function TriagePage({ params }: PageProps<"/claims/[claimId]/triage">) {
  const { claimId } = await params;

  // Voir la note sur le soft 404 dans ../page.tsx.
  const detail = await fetchClaimDetail(claimId).catch((error: unknown) => {
    if (error instanceof ApiNotFoundError) return null;
    throw error;
  });

  if (!detail) notFound();

  const { claim, policy } = detail;

  return (
    <PageContainer className="space-y-8">
      <PageHeader
        eyebrow={<TypeSinistreBadge type={claim.type_sinistre} />}
        title={
          <>
            Triage de <span className="font-mono">{claim.claim_id}</span>
          </>
        }
        description={`Police ${policy.policy_id} · ${policy.assure} · ${policy.vehicule}`}
        actions={
          <Button asChild variant="outline">
            <Link href={`/claims/${claim.claim_id}`}>
              <ArrowLeft aria-hidden="true" />
              Retour au dossier
            </Link>
          </Button>
        }
      />

      <TriageRunView claimId={claim.claim_id} />
    </PageContainer>
  );
}
