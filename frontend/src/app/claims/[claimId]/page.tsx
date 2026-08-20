import { Play } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BlessureFlag, InjectionFlag } from "@/components/claims/claim-flags";
import { DeterministicAnalysis } from "@/components/claims/deterministic-analysis";
import { ClaimFactsPanel, PolicyPanel } from "@/components/claims/policy-panel";
import { UntrustedTextPanel } from "@/components/claims/untrusted-text-panel";
import { PageContainer, PageHeader } from "@/components/layout/page-container";
import { TypeSinistreBadge } from "@/components/status/domain-badges";
import { Button } from "@/components/ui/button";
import { ApiNotFoundError, fetchClaimDetail } from "@/lib/api-server";
import { formatDate } from "@/lib/status";

/**
 * Fiche dossier. Server Component, aucun appel de modele : tout ce qui est
 * affiche ici est lu dans les CSV ou calcule par les tools deterministes.
 */
// Voir la note de src/app/page.tsx : rendu a chaque requete.
export const dynamic = "force-dynamic";

export default async function FicheDossierPage({
  params,
}: PageProps<"/claims/[claimId]">) {
  // Next 16 : `params` est une promesse.
  const { claimId } = await params;

  // SOFT 404 ASSUME : cette page a un loading.tsx, donc la reponse a deja
  // commence a etre diffusee quand le sinistre se revele absent. Next rend
  // alors not-found.tsx avec un statut 200 et une balise noindex - le code
  // 404 ne peut plus etre change une fois le flux ouvert. Obtenir un vrai 404
  // imposerait de verifier l'existence du dossier dans proxy.ts, soit un
  // aller-retour supplementaire vers l'API sur CHAQUE affichage de fiche.
  // Pour une console interne, sans enjeu de referencement, l'echange n'en
  // vaut pas la peine.
  const detail = await fetchClaimDetail(claimId).catch((error: unknown) => {
    if (error instanceof ApiNotFoundError) return null;
    throw error;
  });

  if (!detail) notFound();

  const { claim, policy, coverage, repair_band, fraud_signals, screening } = detail;

  return (
    <PageContainer className="space-y-8">
      <PageHeader
        eyebrow={
          <>
            <TypeSinistreBadge type={claim.type_sinistre} />
            {claim.blessure === "oui" ? <BlessureFlag /> : null}
            {screening.markers_found.length > 0 ? (
              <InjectionFlag markers={screening.markers_found} />
            ) : null}
          </>
        }
        title={<span className="font-mono">{claim.claim_id}</span>}
        description={`Déclaré le ${formatDate(claim.date_sinistre)} · police ${policy.policy_id} · ${policy.assure}`}
        actions={
          <Button asChild>
            <Link href={`/claims/${claim.claim_id}/triage`}>
              <Play aria-hidden="true" />
              Lancer le triage
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <UntrustedTextPanel claimId={claim.claim_id} screening={screening} />
          <ClaimFactsPanel claim={claim} />
        </div>
        <PolicyPanel policy={policy} />
      </div>

      <DeterministicAnalysis
        coverage={coverage}
        repairBand={repair_band}
        fraudSignals={fraud_signals}
      />
    </PageContainer>
  );
}
