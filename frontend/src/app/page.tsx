import { ClaimsFilterBar } from "@/components/claims/claims-filter-bar";
import { ClaimsTable } from "@/components/claims/claims-table";
import { DatasetBar } from "@/components/dataset/dataset-bar";
import { DatasetUpload } from "@/components/dataset/dataset-upload";
import { PageContainer, PageHeader } from "@/components/layout/page-container";
import { fetchClaims, fetchDatasetState } from "@/lib/api-server";
import {
  datesIncoherentes,
  filtrerClaims,
  filtresActifs,
  lireFiltres,
} from "@/lib/claims-filter";

/**
 * Page d'accueil.
 *
 * TROIS etats, jamais melanges - et le troisieme ne doit surtout pas etre pris
 * pour le premier :
 *
 *   1. aucun fichier depose  -> on demande les fichiers ;
 *   2. des dossiers charges  -> la file d'attente ;
 *   3. des dossiers charges, mais aucun ne passe les filtres -> une file vide
 *      QUI DIT POURQUOI, et qui propose de retirer les filtres.
 *
 * Confondre 1 et 3 ferait croire a une perte de donnees. C'est ClaimsTable qui
 * porte la distinction, via `filtresActifs`.
 *
 * Il n'existe toujours pas d'etat ou l'ecran montrerait des donnees venues
 * d'ailleurs.
 */

// Rendu a chaque requete : le jeu de donnees vit dans le serveur d'API et peut
// changer a tout moment. La lecture de searchParams rend de toute facon la
// route dynamique ; ce drapeau reste la pour la premiere raison.
export const dynamic = "force-dynamic";

export default async function AccueilPage({ searchParams }: PageProps<"/">) {
  const dataset = await fetchDatasetState();

  if (!dataset.loaded) {
    return (
      <PageContainer className="space-y-8">
        <DatasetUpload />
      </PageContainer>
    );
  }

  const claims = await fetchClaims();

  // Next 16 : searchParams est une promesse.
  // Le filtrage se fait ici, cote serveur, sur la liste complete : le tableau
  // reste un composant de presentation et le navigateur ne recoit que la barre
  // de filtres en JavaScript. Chaque changement de filtre relit l'API - c'est
  // le bon compromis pour une console mono-utilisateur sur un jeu depose, et
  // le delai de saisie limite cela a une requete par pause.
  const filtres = lireFiltres(await searchParams);
  const visibles = filtrerClaims(claims, filtres);
  const nbFiltres = filtresActifs(filtres);

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        title="File d'attente"
        description={
          <span role="status" aria-live="polite">
            {nbFiltres > 0
              ? `${visibles.length} sur ${claims.length} déclarations affichées. `
              : `${claims.length} déclarations à traiter. `}
            Ouvrez un dossier pour voir le détail et lancer son analyse.
          </span>
        }
      />
      <DatasetBar state={dataset} />
      <ClaimsFilterBar datesIncoherentes={datesIncoherentes(filtres)} />
      <ClaimsTable claims={visibles} filtresActifs={nbFiltres > 0} />
    </PageContainer>
  );
}
