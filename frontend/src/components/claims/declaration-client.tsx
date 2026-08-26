import type { Screening } from "@/lib/types";

/**
 * Le texte du client, tel qu'il l'a ecrit.
 *
 * Extrait de client-message-panel.tsx pour que la fiche dossier ET l'ecran
 * d'analyse montrent exactement la meme chose. C'est le seul endroit du
 * frontend qui decide comment presenter une declaration client.
 *
 * CHOIX DE LECTURE : le gestionnaire humain lit TOUJOURS le texte d'origine
 * (screening.original_text), y compris quand il a ete signale. Ce texte est
 * rendu inerte par React - jamais dangerouslySetInnerHTML - donc le lire ne
 * declenche rien. Ce que le texte signale ne touche PAS, c'est le modele : le
 * triage ne voit que la version assainie ou le placeholder (text_for_model).
 * Lisible par l'humain, invisible pour le modele.
 *
 * Le fait qu'un message ait ete signale n'est PAS rappele ici : sur la fiche
 * dossier (avant analyse) le texte se lit simplement tel quel, et l'ecran
 * d'analyse le signale une fois le triage termine (triage-run-view.tsx). C'est
 * `messageEstSignale`, exporte ci-dessous, qui alimente cette note.
 *
 * Composant de presentation pur, sans "use client" : il n'a ni etat ni effet,
 * et peut donc etre rendu par un Server Component sans embarquer de
 * JavaScript.
 */

/** Retire l'encadrement technique que le backend ajoute autour du texte
 *  transmis au modele. Sans effet sur original_text, qui n'en porte pas. */
export function texteLisible(brut: string): string {
  return brut.replace(/<\/?donnee_client_non_fiable>/g, "").trim();
}

/** Un message est "signale" quand le filtre l'a ecarte ou y a repere un
 *  marqueur : dans les deux cas le modele ne l'a pas lu tel quel. */
export function messageEstSignale(screening: Screening): boolean {
  return screening.redacted || screening.markers_found.length > 0;
}

export function DeclarationClient({ screening }: { screening: Screening }) {
  const texte = texteLisible(screening.original_text);

  if (texte === "") {
    return (
      <p className="text-sm text-muted-foreground">
        Le client n&apos;a joint aucun texte à sa déclaration.
      </p>
    );
  }

  return (
    <blockquote className="border-l-2 pl-3 text-sm leading-relaxed whitespace-pre-line">
      {texte}
    </blockquote>
  );
}
