"use client";

import { BookOpen, ChevronDown } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchRules } from "@/lib/api-client";
import { devGroup, devWarn } from "@/lib/dev-log";
import { COMMENT_CA_FONCTIONNE } from "@/lib/how-it-works";
import type { RulesDocument } from "@/lib/types";

/**
 * L'aide de l'application, a un clic de n'importe quelle page.
 *
 * DEUX NIVEAUX, DANS CET ORDRE.
 *
 * D'abord une explication en langage courant (lib/how-it-works.ts). Le texte
 * de reference a ete ecrit pour le modele et pour le developpeur : il parle en
 * identifiants, il arrive sans mise en forme, et il suppose de connaitre le
 * contrat de sortie. Un gestionnaire de sinistres n'a pas a apprendre ce
 * vocabulaire pour savoir ce que l'application fait de ses dossiers.
 *
 * Ensuite, replie, le texte de reference lui-meme, mot pour mot et sans
 * reformulation. Il n'est pas retire : c'est LUI qui fait foi, et le panneau
 * le dit. Si les deux divergeaient un jour, ce sont ces regles-la qui
 * s'appliquent, et la reformulation qui serait fausse.
 *
 * LE CHARGEMENT SUIT CE DECOUPAGE. L'explication est statique et s'affiche
 * instantanement ; l'appel a l'API ne part qu'a l'ouverture du bloc de
 * reference. Ouvrir le panneau, lire, refermer ne coute donc aucune requete -
 * et si le backend est eteint, seul ce bloc echoue, pas toute l'aide.
 */
export function HowItWorksSheet() {
  const [documents, setDocuments] = React.useState<RulesDocument[] | null>(null);
  const [erreur, setErreur] = React.useState<string | null>(null);
  const [chargement, setChargement] = React.useState(false);

  function chargerSiNecessaire(ouvert: boolean) {
    if (!ouvert || documents || chargement) return;
    setChargement(true);
    setErreur(null);
    fetchRules()
      .then((rules) => {
        // contrat_sortie.md decrit le format JSON attendu du modele : c'est
        // une specification technique, sans utilite pour un gestionnaire. Seul
        // le texte des regles metier est montre ici.
        devGroup("documents de référence", rules.documents);
        setDocuments(rules.documents.filter((d) => d.name === "regles_sinistres.md"));
      })
      .catch((e: Error) => {
        devWarn("chargement des règles", e);
        setErreur("Les règles n'ont pas pu être chargées.");
      })
      .finally(() => setChargement(false));
  }

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm">
          <BookOpen aria-hidden="true" />
          {/* Le libelle est long : sous `sm`, l'icone porte seule, avec un nom
              accessible pour le clavier et les lecteurs d'ecran. */}
          <span className="hidden sm:inline">Comment ça fonctionne</span>
          <span className="sr-only sm:hidden">Comment ça fonctionne</span>
        </Button>
      </SheetTrigger>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-2xl">
        <SheetHeader className="border-b">
          <SheetTitle>Comment ça fonctionne</SheetTitle>
          <SheetDescription>
            Ce que TSA fait de vos dossiers, et sur quelles règles il s&apos;appuie.
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-8 p-6">
            {COMMENT_CA_FONCTIONNE.map((section) => {
              // La provenance se signale au niveau le plus haut possible. Une
              // section entierement issue de choix applicatifs le dit une fois
              // sous son titre ; repeter la mention a chaque puce noierait le
              // texte que le gestionnaire est venu lire. Seules les sections
              // MELANGEES marquent point par point - c'est la qu'on risque
              // vraiment de prendre un choix pour une regle.
              const homogene = section.points.every(
                (p) => p.origine === section.points[0].origine,
              );
              const toutApplicatif = homogene && section.points[0].origine === "application";

              return (
                <section key={section.titre} className="space-y-2">
                  <h3 className="font-medium">{section.titre}</h3>
                  {section.intro ? (
                    <p className="text-sm text-muted-foreground">{section.intro}</p>
                  ) : null}
                  {toutApplicatif ? (
                    <p className="text-xs text-muted-foreground">
                      Choix de cette application : ces points ne figurent dans aucun
                      document de référence.
                    </p>
                  ) : null}
                  <ul className="space-y-2">
                    {section.points.map((point) => (
                      <li
                        key={point.texte}
                        className="text-sm leading-relaxed before:mr-2 before:text-muted-foreground before:content-['—']"
                      >
                        {point.texte}
                        {!homogene && point.origine === "application" ? (
                          <span className="ml-1.5 text-xs text-muted-foreground">
                            (choix de l&apos;application)
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}

            <Separator />

            <Collapsible onOpenChange={chargerSiNecessaire}>
              <p className="mb-2 text-sm text-muted-foreground">
                C&apos;est ce texte qui fait foi. En cas d&apos;écart avec
                l&apos;explication ci-dessus, ce sont ces règles qui s&apos;appliquent.
              </p>
              <CollapsibleTrigger asChild>
                <Button variant="outline" size="sm" className="w-full">
                  Afficher le texte de référence (regles_sinistres.md)
                  <ChevronDown
                    className="ml-auto transition-transform [[data-state=open]>&]:rotate-180"
                    aria-hidden="true"
                  />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-4">
                {chargement ? (
                  <div className="space-y-3" aria-busy="true">
                    <Skeleton className="h-5 w-48" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-11/12" />
                    <Skeleton className="h-4 w-4/5" />
                  </div>
                ) : null}

                {erreur ? (
                  <p className="text-sm text-destructive">
                    Impossible de charger les documents : {erreur}
                  </p>
                ) : null}

                {documents?.map((document) => (
                  <article
                    key={document.name}
                    className="text-sm leading-relaxed whitespace-pre-wrap"
                  >
                    {document.content}
                  </article>
                ))}
              </CollapsibleContent>
            </Collapsible>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
