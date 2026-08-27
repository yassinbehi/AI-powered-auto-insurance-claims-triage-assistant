import { History } from "lucide-react";

import { AnalysesTable } from "@/components/analyses/analyses-table";
import { PageContainer, PageHeader } from "@/components/layout/page-container";
import { fetchAnalyses } from "@/lib/api-server";

/**
 * Les cas deja analyses.
 *
 * Une analyse coute un appel de modele et plusieurs dizaines de secondes.
 * Sans cette page, son resultat disparaissait a la fermeture de l'onglet et
 * relire une conclusion de la veille demandait de la racheter.
 *
 * L'historique ne depend PAS du jeu de donnees ouvert : il montre tout ce qui
 * a ete analyse sur cette machine, jeu par jeu, y compris les analyses de jeux
 * supprimes depuis. C'est ce qui en fait une trace de la depense engagee, et
 * non une seconde file d'attente.
 */

// Rendu a chaque requete : une analyse lancee depuis un autre onglet doit
// apparaitre ici sans avoir a vider un cache.
export const dynamic = "force-dynamic";

export default async function AnalysesPage() {
  const analyses = await fetchAnalyses();

  const total = analyses.reduce((somme, a) => somme + a.cost_usd, 0);

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <History className="size-4" aria-hidden="true" />
            Historique
          </span>
        }
        title="Cas analysés"
        description={
          analyses.length === 0 ? (
            "Aucune analyse pour l'instant."
          ) : (
            <span role="status" aria-live="polite">
              {analyses.length} analyse{analyses.length > 1 ? "s" : ""} conservée
              {analyses.length > 1 ? "s" : ""}, pour un coût total de{" "}
              <span className="font-mono tabular-nums">
                {total.toLocaleString("fr-FR", {
                  style: "currency",
                  currency: "USD",
                  minimumFractionDigits: 4,
                  maximumFractionDigits: 4,
                })}
              </span>
              . Ouvrez une ligne pour relire la conclusion.
            </span>
          )
        }
      />
      <AnalysesTable analyses={analyses} />
    </PageContainer>
  );
}
