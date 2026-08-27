"use client";

import { LoaderCircle, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { deleteAnalyse } from "@/lib/api-client";
import { devWarn } from "@/lib/dev-log";

/**
 * Retrait d'une analyse de l'historique.
 *
 * Derriere une confirmation : l'analyse a coute un appel de modele, et la
 * supprimer ne la rembourse pas - la relancer se paierait une seconde fois.
 * C'est aussi la seule action destructrice de cet ecran, au milieu d'une page
 * qui ne fait que relire.
 */
export function SupprimerAnalyse({ id, claimId }: { id: number; claimId: string }) {
  const router = useRouter();
  const [enCours, setEnCours] = React.useState(false);

  async function supprimer() {
    setEnCours(true);
    try {
      await deleteAnalyse(id);
      toast.success("Analyse retirée de l'historique.");
      // replace et non push : la page qu'on quitte n'existe plus, et un retour
      // arriere y ramenerait sur un 404.
      router.replace("/analyses");
      router.refresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      devWarn("suppression d'une analyse", e);
      toast.error(message);
      setEnCours(false);
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={enCours}
      onClick={() =>
        toast(`Retirer l'analyse de ${claimId} ?`, {
          description:
            "Elle disparaîtra de l'historique. La relancer coûterait un nouvel appel au modèle.",
          action: { label: "Retirer", onClick: () => void supprimer() },
          cancel: { label: "Annuler", onClick: () => {} },
        })
      }
    >
      {enCours ? (
        <LoaderCircle className="animate-spin" aria-hidden="true" />
      ) : (
        <Trash2 aria-hidden="true" />
      )}
      Retirer de l&apos;historique
    </Button>
  );
}
