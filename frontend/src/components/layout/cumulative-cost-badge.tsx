"use client";

import { Coins } from "lucide-react";
import { toast } from "sonner";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  formaterCout,
  reinitialiserCoutCumule,
  useCoutCumule,
  useHydrate,
} from "@/lib/cumulative-cost";
import { cn } from "@/lib/utils";

/**
 * Cout CUMULE de toutes les analyses lancees depuis ce navigateur, affiche en
 * tete de chaque page (AppHeader vit dans le layout racine).
 *
 * Ce n'est pas le cout de l'analyse en cours : le detail par execution part
 * dans la console avec le reste de la matiere technique (voir
 * hooks/use-triage-stream.ts). Ce qu'un utilisateur ne peut PAS reconstituer
 * seul, en revanche, c'est ce qu'il a depense en tout - d'ou un total qui
 * survit au rechargement, tenu par lib/cumulative-cost.ts.
 *
 * Le total apparait meme a zero : un compteur de depense qui n'existe qu'une
 * fois la depense engagee ne previent personne.
 */
export function CumulativeCostBadge() {
  const cumul = useCoutCumule();

  // Le rendu serveur ne connait aucun localStorage et affiche donc toujours
  // zero. Tant que l'hydratation n'a pas eu lieu, le montant est masque plutot
  // qu'affiche a "0,0000 $US" : un faux chiffre, meme fugace, se lit comme une
  // information. L'espace, lui, reste reserve - pas de saut de mise en page.
  const hydrate = useHydrate();

  const montant = formaterCout(cumul.total_usd);
  const detail =
    cumul.analyses === 0
      ? "Aucune analyse comptée pour l'instant."
      : `${cumul.analyses} analyse${cumul.analyses > 1 ? "s" : ""} comptée${
          cumul.analyses > 1 ? "s" : ""
        }.`;

  function demanderReinitialisation() {
    if (cumul.analyses === 0 && cumul.total_usd === 0) return;

    toast("Remettre le compteur à zéro ?", {
      description: `${montant} cumulés sur ${detail.toLowerCase()}`,
      action: {
        label: "Réinitialiser",
        onClick: () => {
          reinitialiserCoutCumule();
          toast.success("Compteur de coût remis à zéro.");
        },
      },
      cancel: { label: "Annuler", onClick: () => {} },
    });
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={demanderReinitialisation}
          // `tabular-nums` : les chiffres gardent la meme largeur d'une valeur
          // a l'autre, sinon le total tressaute a chaque analyse.
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          aria-label={`Coût cumulé des analyses : ${montant}. ${detail} Activer pour remettre à zéro.`}
        >
          <Coins className="size-4 shrink-0" aria-hidden="true" />
          <span className="sr-only">Coût cumulé</span>
          <span className={cn("font-mono tabular-nums", hydrate ? null : "invisible")}>
            {montant}
          </span>
        </button>
      </TooltipTrigger>
      {/* Une seule phrase, celle qui dit quoi faire. Le detail (portee du
          compteur, nombre d'analyses) reste accessible autrement : libelle
          lecteur d'ecran ci-dessus, et resume dans la demande de remise a
          zero. Une infobulle qui explique plus qu'elle ne guide se lit une
          fois puis gene a chaque survol. */}
      <TooltipContent>Cliquer pour remettre à zéro.</TooltipContent>
    </Tooltip>
  );
}
