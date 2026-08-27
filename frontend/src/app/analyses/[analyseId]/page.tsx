import { ArrowLeft, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { SupprimerAnalyse } from "@/components/analyses/supprimer-analyse";
import { PageContainer, PageHeader } from "@/components/layout/page-container";
import { TriageResultCard } from "@/components/result/triage-result-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiNotFoundError, fetchAnalyse } from "@/lib/api-server";
import { formatDateHeure, formatUsd } from "@/lib/status";

/**
 * Une analyse conservee, relue.
 *
 * Le resultat s'affiche avec le MEME composant que juste apres l'analyse
 * (TriageResultCard) : une conclusion relue trois jours plus tard doit se lire
 * exactement comme le jour ou elle a ete produite, sans avoir a retrouver ses
 * reperes dans une seconde presentation.
 *
 * Ce qui s'y ajoute est ce que le direct n'avait pas besoin de dire : quand,
 * sur quel jeu de donnees, avec quel modele, et pour quel cout.
 */

export const dynamic = "force-dynamic";

function Metadonnees({
  analyse,
}: {
  analyse: Awaited<ReturnType<typeof fetchAnalyse>>;
}) {
  const lignes = [
    ["Assuré", analyse.assure || "—"],
    ["Analysé le", formatDateHeure(analyse.analyse_le)],
    ["Jeu de données", analyse.dataset_nom || "—"],
    ["Modèle", analyse.model || "—"],
    ["Coût", formatUsd(analyse.cost_usd)],
  ] as const;

  return (
    <Card>
      <CardContent>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
          {lignes.map(([libelle, valeur]) => (
            <div key={libelle}>
              <dt className="text-xs text-muted-foreground">{libelle}</dt>
              <dd className="text-sm font-medium tabular-nums">{valeur}</dd>
            </div>
          ))}
        </dl>
        {/* Le jeu d'origine a disparu : le nom reste lisible (il est recopie a
            l'enregistrement) mais le dossier n'est plus ouvrable. Le dire vaut
            mieux qu'un lien qui menerait a une page introuvable. */}
        {analyse.dataset_id === null && analyse.dataset_nom ? (
          <p className="mt-4 text-xs text-muted-foreground">
            Le jeu de données « {analyse.dataset_nom} » a été supprimé depuis :
            le dossier d&apos;origine n&apos;est plus consultable.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default async function AnalysePage({
  params,
}: PageProps<"/analyses/[analyseId]">) {
  const { analyseId } = await params;

  const identifiant = Number(analyseId);
  // Un identifiant non numerique n'atteindra jamais l'API : autant le traiter
  // ici comme l'introuvable qu'il est.
  if (!Number.isInteger(identifiant) || identifiant < 1) notFound();

  const analyse = await fetchAnalyse(identifiant).catch((error: unknown) => {
    if (error instanceof ApiNotFoundError) return null;
    throw error;
  });
  if (analyse === null) notFound();

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        eyebrow={
          <Button asChild variant="ghost" size="sm" className="-ml-2 h-auto px-2 py-1">
            <Link href="/analyses">
              <ArrowLeft aria-hidden="true" />
              Cas analysés
            </Link>
          </Button>
        }
        title={analyse.claim_id}
        description="Analyse conservée. Relisez la conclusion telle qu'elle a été produite."
        actions={<SupprimerAnalyse id={analyse.id} claimId={analyse.claim_id} />}
      />

      <Metadonnees analyse={analyse} />

      {analyse.output ? (
        <TriageResultCard output={analyse.output} />
      ) : (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>Cette analyse n&apos;a pas abouti</AlertTitle>
          <AlertDescription>
            {analyse.erreur ??
              "L'analyse s'est interrompue avant de produire une conclusion."}{" "}
            Elle a malgré tout été facturée, d&apos;où sa présence ici. Vous pouvez
            la relancer depuis le dossier.
          </AlertDescription>
        </Alert>
      )}

      {analyse.dataset_id !== null ? (
        <Button asChild variant="outline">
          <Link href={`/claims/${encodeURIComponent(analyse.claim_id)}`}>
            Ouvrir le dossier {analyse.claim_id}
          </Link>
        </Button>
      ) : null}
    </PageContainer>
  );
}
