import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { ClaimBrief } from "@/components/claims/claim-brief";
import { messageEstSignale } from "@/components/claims/declaration-client";
import { PageContainer, PageHeader } from "@/components/layout/page-container";
import { TypeSinistreBadge } from "@/components/status/domain-badges";
import { TriageRunView } from "@/components/triage/triage-run-view";
import { Button } from "@/components/ui/button";
import {
  ApiNoDatasetError,
  ApiNotFoundError,
  fetchClaimDetail,
  fetchModels,
} from "@/lib/api-server";

/**
 * Page de triage. Le contexte du dossier est rendu cote serveur (gratuit) ;
 * seul le deroule du triage est un composant client, parce qu'il consomme un
 * flux SSE.
 *
 * ClaimBrief est construit ici, cote serveur, mais AFFICHE par TriageRunView :
 * il n'apparait qu'une fois l'analyse lancee. Il est passe en prop plutot que
 * rendu directement pour rester un Server Component - le composant client
 * decide QUAND le montrer, sans que son contenu ne parte dans le bundle.
 *
 * L'ordre de lecture reste delibere : une fois l'analyse lancee, de quoi parle
 * le dossier vient avant ce qu'il faut en faire. L'ecran donnait auparavant une
 * prochaine action et un message a envoyer sans jamais dire quel sinistre etait
 * en cause, ce qui obligeait a revenir en arriere pour comprendre ce qu'on
 * validait.
 */
// Voir la note de src/app/page.tsx : rendu a chaque requete.
export const dynamic = "force-dynamic";

export default async function TriagePage({ params }: PageProps<"/claims/[claimId]/triage">) {
  const { claimId } = await params;

  // Voir la note sur le soft 404 dans ../page.tsx.
  const resultat = await fetchClaimDetail(claimId).then(
    (detail) => ({ kind: "ok" as const, detail }),
    (error: unknown) => {
      if (error instanceof ApiNoDatasetError) return { kind: "sans-donnees" as const };
      if (error instanceof ApiNotFoundError) return { kind: "introuvable" as const };
      throw error;
    },
  );

  if (resultat.kind === "sans-donnees") redirect("/");
  if (resultat.kind === "introuvable") notFound();

  const { claim, policy, screening } = resultat.detail;
  // Le detail du dossier a repondu : le backend est joignable. La liste des
  // modeles est accessoire - si elle echoue, on degrade vers une liste vide
  // (selecteur masque, le backend appliquera son modele par defaut).
  const models = await fetchModels().catch(() => []);

  return (
    <PageContainer className="space-y-8">
      <PageHeader
        eyebrow={<TypeSinistreBadge type={claim.type_sinistre} />}
        title={
          <>
            Analyse du dossier <span className="font-mono">{claim.claim_id}</span>
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

      <TriageRunView
        claimId={claim.claim_id}
        models={models}
        messageSignale={messageEstSignale(screening)}
        brief={<ClaimBrief claim={claim} policy={policy} screening={screening} />}
      />
    </PageContainer>
  );
}
