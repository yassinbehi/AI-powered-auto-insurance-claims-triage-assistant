import { History } from "lucide-react";

import { AnalysesSearchBar } from "@/components/analyses/analyses-search-bar";
import { AnalysesTable } from "@/components/analyses/analyses-table";
import { PageContainer, PageHeader } from "@/components/layout/page-container";
import { filtrerAnalyses, lireRecherche, lireTri, trierAnalyses } from "@/lib/analyses-filter";
import { fetchAnalyses } from "@/lib/api-server";
import { formatUsd } from "@/lib/status";

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
 *
 * La recherche et le tri se font ICI, cote serveur, sur la liste complete : le
 * tableau reste un composant de presentation et le navigateur ne recoit en
 * JavaScript que la barre de recherche. Meme repartition que la file
 * d'attente, et meme etat porte par l'URL - un historique cherche et trie se
 * copie-colle.
 *
 * TROIS ETATS, jamais melanges : aucune analyse ; des analyses ; des analyses
 * dont aucune ne correspond a la recherche. Confondre le premier et le
 * troisieme ferait croire a une perte de donnees.
 */

// Rendu a chaque requete : une analyse lancee depuis un autre onglet doit
// apparaitre ici sans avoir a vider un cache.
export const dynamic = "force-dynamic";

export default async function AnalysesPage({ searchParams }: PageProps<"/analyses">) {
  const analyses = await fetchAnalyses();

  // Next 16 : searchParams est une promesse.
  const params = await searchParams;
  const q = lireRecherche(params);
  const tri = lireTri(params);
  const visibles = trierAnalyses(filtrerAnalyses(analyses, q), tri);

  // Le cout affiche suit la recherche : filtrer pour ne voir qu'un jeu de
  // donnees doit repondre "et combien celui-la a-t-il coute ?".
  const total = visibles.reduce((somme, a) => somme + a.cost_usd, 0);

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
              {q !== ""
                ? `${visibles.length} sur ${analyses.length} analyses affichées. `
                : `${analyses.length} analyse${analyses.length > 1 ? "s" : ""} conservée${
                    analyses.length > 1 ? "s" : ""
                  }. `}
              {visibles.length > 0 ? (
                <>
                  Coût{q !== "" ? " de cette sélection" : " total"} :{" "}
                  <span className="font-mono tabular-nums">{formatUsd(total)}</span>.{" "}
                </>
              ) : null}
              Ouvrez une ligne pour relire la conclusion.
            </span>
          )
        }
      />

      {/* Pas de barre de recherche tant qu'il n'y a rien a chercher : elle ne
          proposerait qu'un champ vide au-dessus d'un ecran vide. */}
      {analyses.length > 0 ? <AnalysesSearchBar /> : null}

      <AnalysesTable analyses={visibles} tri={tri} recherche={q !== ""} />
    </PageContainer>
  );
}
