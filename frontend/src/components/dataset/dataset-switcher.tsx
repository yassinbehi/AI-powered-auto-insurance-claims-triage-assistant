"use client";

import { Check, Database, FolderOpen, LoaderCircle, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { activateDataset, deleteDataset } from "@/lib/api-client";
import { devWarn } from "@/lib/dev-log";
import type { DatasetResume } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Passage d'un jeu de donnees a l'autre.
 *
 * Les jeux deposes sont conserves et portent un nom : on revient dessus sans
 * redeposer de fichiers. Deux presentations du meme geste, parce que les deux
 * moments n'ont rien a voir :
 *
 *   - DatasetSwitcher, une liste deroulante compacte, quand un jeu est ouvert
 *     et qu'on travaille (voir DatasetBar) ;
 *   - JeuxEnregistres, une liste depliee, sur l'ecran de depot - la, une
 *     liste deroulante cacherait justement ce qu'il faut montrer : que des
 *     dossiers existent deja et qu'il est inutile de redeposer.
 *
 * DEUX ACTIONS DE NATURES DIFFERENTES cohabitent ici, et c'est le piege :
 * ouvrir un jeu est anodin et reversible, supprimer ne l'est pas. La
 * suppression passe donc par une confirmation, et son bouton n'est jamais sur
 * la trajectoire d'un simple changement.
 */

/** Ouvrir / supprimer, avec l'etat d'attente et le rafraichissement de la
 *  page. Partage par les deux presentations ci-dessous. */
function useActions() {
  const router = useRouter();
  const [enCours, setEnCours] = React.useState(false);

  async function ouvrir(jeu: DatasetResume) {
    if (jeu.actif || enCours) return;

    setEnCours(true);
    try {
      const etat = await activateDataset(jeu.id);
      toast.success(`« ${etat.nom} » ouvert : ${etat.claims_count} déclarations.`);
      // La file d'attente est rendue cote serveur : sans ce rafraichissement,
      // l'ecran continuerait d'afficher les dossiers du jeu precedent.
      router.refresh();
    } catch (e) {
      // 409 : une analyse tourne. Le backend refuse de remplacer les dossiers
      // sous une boucle agentique en cours, et son message le dit deja.
      const message = e instanceof Error ? e.message : String(e);
      devWarn("changement de jeu de données", e);
      toast.error(message);
    } finally {
      setEnCours(false);
    }
  }

  async function supprimer(jeu: DatasetResume) {
    setEnCours(true);
    try {
      await deleteDataset(jeu.id);
      toast.success(`« ${jeu.nom} » supprimé.`);
      router.refresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      devWarn("suppression d'un jeu de données", e);
      toast.error(message);
    } finally {
      setEnCours(false);
    }
  }

  function demanderSuppression(jeu: DatasetResume) {
    toast(`Supprimer « ${jeu.nom} » ?`, {
      description: jeu.actif
        ? "C'est le jeu ouvert : l'application reviendra à l'écran de dépôt. C'est définitif."
        : `${jeu.claims_count} déclarations et ${jeu.policies_count} contrats. C'est définitif.`,
      action: { label: "Supprimer", onClick: () => void supprimer(jeu) },
      cancel: { label: "Annuler", onClick: () => {} },
    });
  }

  return { enCours, ouvrir, demanderSuppression };
}

function BoutonSupprimer({
  jeu,
  onDemander,
}: {
  jeu: DatasetResume;
  onDemander: (jeu: DatasetResume) => void;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-7 shrink-0 text-muted-foreground hover:text-destructive"
      aria-label={`Supprimer ${jeu.nom}`}
      onClick={(e) => {
        // Sans cela, le clic remonterait a la ligne et OUVRIRAIT le jeu qu'on
        // cherche a supprimer.
        e.stopPropagation();
        onDemander(jeu);
      }}
    >
      <Trash2 aria-hidden="true" />
    </Button>
  );
}

/** Liste deroulante, pour la barre de la file d'attente. */
export function DatasetSwitcher({ datasets }: { datasets: DatasetResume[] }) {
  const { enCours, ouvrir, demanderSuppression } = useActions();

  if (datasets.length === 0) return null;
  const actif = datasets.find((d) => d.actif) ?? null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={enCours}>
          {enCours ? (
            <LoaderCircle className="animate-spin" aria-hidden="true" />
          ) : (
            <Database aria-hidden="true" />
          )}
          <span className="max-w-[12rem] truncate">
            {actif ? actif.nom : "Choisir un jeu"}
          </span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Jeux enregistrés ({datasets.length})</DropdownMenuLabel>
        <DropdownMenuSeparator />

        {datasets.map((jeu) => (
          <DropdownMenuItem
            key={jeu.id}
            // preventDefault : fermer le menu au clic sur la corbeille
            // masquerait la demande de confirmation derriere l'animation.
            onSelect={(e) => {
              e.preventDefault();
              void ouvrir(jeu);
            }}
            className="gap-2"
          >
            <Check
              className={cn("size-4 shrink-0", jeu.actif ? "opacity-100" : "opacity-0")}
              aria-hidden="true"
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{jeu.nom}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {jeu.claims_count} déclarations · {jeu.claims_filename}
              </span>
            </span>
            <BoutonSupprimer jeu={jeu} onDemander={demanderSuppression} />
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * Liste depliee, pour l'ecran de depot.
 *
 * Sans elle, fermer un jeu donnerait un ecran qui reclame des fichiers sans
 * dire que ceux d'hier sont toujours la - et l'utilisateur redeposerait ce
 * qu'il possede deja.
 */
export function JeuxEnregistres({ datasets }: { datasets: DatasetResume[] }) {
  const { enCours, ouvrir, demanderSuppression } = useActions();

  if (datasets.length === 0) return null;

  return (
    <div className="mx-auto w-full max-w-2xl space-y-2">
      <h2 className="text-sm font-medium">
        Ou rouvrez un jeu déjà enregistré
      </h2>
      <ul className="divide-y rounded-lg border">
        {datasets.map((jeu) => (
          <li key={jeu.id} className="flex items-center gap-3 px-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{jeu.nom}</p>
              <p className="truncate text-xs text-muted-foreground">
                {jeu.claims_count} déclarations, {jeu.policies_count} contrats ·{" "}
                {jeu.claims_filename}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={enCours}
              onClick={() => void ouvrir(jeu)}
            >
              {enCours ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <FolderOpen aria-hidden="true" />
              )}
              Ouvrir
            </Button>
            <BoutonSupprimer jeu={jeu} onDemander={demanderSuppression} />
          </li>
        ))}
      </ul>
    </div>
  );
}
