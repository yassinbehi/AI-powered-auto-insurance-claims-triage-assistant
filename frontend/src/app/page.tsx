import { ClaimsTable } from "@/components/claims/claims-table";
import { PageContainer, PageHeader } from "@/components/layout/page-container";
import { fetchClaims } from "@/lib/api-server";

/**
 * File d'attente. Server Component : la liste vient des CSV via l'API, sans
 * aucun appel de modele, donc sans latence ni cout.
 */

// Rendu a chaque requete : les CSV sont relus cote Python a chaque appel, et
// figer cette page a la compilation la rendrait fausse des la premiere
// modification des donnees. Rend aussi le build independant du backend.
export const dynamic = "force-dynamic";
export default async function FileDAttentePage() {
  const claims = await fetchClaims();

  return (
    <PageContainer className="space-y-8">
      <PageHeader
        title="File d'attente"
        description={
          <>
            {claims.length} déclarations à trier. Cette liste et les fiches dossier sont
            calculées de façon déterministe : l&apos;agent n&apos;intervient qu&apos;au
            lancement d&apos;un triage.
          </>
        }
      />
      <ClaimsTable claims={claims} />
    </PageContainer>
  );
}
