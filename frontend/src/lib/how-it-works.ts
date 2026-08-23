/**
 * Reformulation en langage courant de data/regles_sinistres.md, pour un
 * gestionnaire de sinistres.
 *
 * POURQUOI CE FICHIER EXISTE. Le texte de reference a ete ecrit pour le modele
 * et pour le developpeur : il parle en identifiants (`expertise_requise`,
 * `rc_simple`), il est servi sans rendu markdown, et il suppose de connaitre
 * le contrat de sortie. Un gestionnaire n'a pas a apprendre ce vocabulaire
 * pour comprendre ce que l'application fait de ses dossiers.
 *
 * CE QUI N'EST PAS FAIT ICI. Rien n'est remplace. Le texte de reference reste
 * accessible dans le meme panneau, en dessous, mot pour mot, et c'est LUI qui
 * fait foi. La reformulation est un confort de lecture, pas une autorite.
 *
 * OBLIGATION DE MAINTENANCE. Si data/regles_sinistres.md change, ce fichier
 * doit etre relu ligne a ligne. C'est le prix de toute reformulation, et c'est
 * exactement pourquoi elle vit dans un module structure plutot que dispersee
 * dans du JSX : chaque point est ici confrontable a sa source.
 *
 * `origine: "application"` marque les points qui ne figurent dans AUCUN
 * document et sont des choix de cette application - meme distinction que
 * data/origine_des_regles.md, et meme statut : discutables.
 */

export interface PointExplique {
  texte: string;
  origine: "document" | "application";
}

export interface SectionExpliquee {
  titre: string;
  intro?: string;
  points: PointExplique[];
}

/** Raccourcis de lecture : la majorite des points d'une section partagent la
 *  meme origine. */
const doc = (texte: string): PointExplique => ({ texte, origine: "document" });
const app = (texte: string): PointExplique => ({ texte, origine: "application" });

export const COMMENT_CA_FONCTIONNE: SectionExpliquee[] = [
  {
    titre: "Ce que fait TSA",
    points: [
      app(
        "TSA lit les deux fichiers que vous déposez — vos déclarations et vos contrats — et prépare chaque dossier : la garantie du contrat, les pièces attendues, le montant du devis, les points de vigilance.",
      ),
      app(
        "Quand vous le demandez, dossier par dossier, il propose un classement, la prochaine action à mener et un brouillon de réponse au client.",
      ),
      app(
        "Tout ce qu'il produit est une proposition. La décision reste la vôtre.",
      ),
    ],
  },
  {
    titre: "Ce qu'il ne fait jamais",
    intro:
      "Ces quatre actions lui sont interdites, quelles que soient les circonstances et quoi que demande le client.",
    points: [
      doc("Valider un paiement."),
      doc("Rejeter définitivement une demande."),
      doc("Modifier un contrat d'assurance."),
      doc("Clôturer un sinistre."),
    ],
  },
  {
    titre: "Ce qui est calculé sans rien lancer",
    intro:
      "Dès le dépôt de vos fichiers, et sans aucune analyse, chaque dossier affiche déjà :",
    points: [
      app("La garantie applicable, d'après la formule du contrat."),
      app("Les pièces obligatoires pour ce type de sinistre."),
      app("La fourchette de réparation, et si le devis dépasse 5 000 TND."),
      app("Les points de vigilance lisibles dans les colonnes du fichier."),
      app("Le repérage d'un message client qui demanderait d'ignorer les règles."),
      app("L'urgence estimée dans la file d'attente."),
      app(
        "Rien de tout cela ne consomme d'analyse. L'analyse complète ne démarre que si vous ouvrez un dossier et cliquez sur « Lancer l'analyse ».",
      ),
    ],
  },
  {
    titre: "Les règles de couverture",
    intro: "Ce que couvre chaque formule de contrat.",
    points: [
      doc("RC simple : uniquement la responsabilité civile envers les tiers."),
      doc(
        "Tiers plus : la responsabilité civile, le bris de glace, le vol et l'incendie, selon les garanties listées au contrat.",
      ),
      doc("Tous risques : la collision et les dommages au véhicule assuré, sauf exclusion."),
      doc(
        "Flotte pro : les véhicules professionnels, si le conducteur est habilité et l'usage conforme.",
      ),
    ],
  },
  {
    titre: "Les pièces obligatoires",
    intro: "Ce qu'un dossier doit contenir selon le type de sinistre.",
    points: [
      doc("Collision : le constat, des photos, un devis."),
      doc("Vol : le dépôt de plainte, la carte grise, les clés, une déclaration circonstanciée."),
      doc("Incendie : des photos, le rapport de remorquage, et une expertise obligatoire."),
      doc("Bris de glace : des photos et un devis."),
    ],
  },
  {
    titre: "Quand un dossier doit être escaladé",
    points: [
      doc("Une blessure est déclarée : expertise requise, priorité critique."),
      doc("Le devis dépasse 5 000 TND : expertise obligatoire."),
      doc("Le conducteur n'est pas déclaré, ou n'est pas habilité : votre validation est requise."),
      doc(
        "Le message du client demande d'ignorer les règles : ce contenu n'est pas fiable, il n'est pas suivi.",
      ),
      doc(
        "Plusieurs de ces éléments se combinent — déclaration tardive, montant élevé, incohérence avec le contrat, vol récent, pièces insuffisantes : le dossier est signalé comme suspect à vérifier.",
      ),
    ],
  },
  {
    titre: "L'urgence estimée dans la file",
    intro:
      "L'urgence est un repère de lecture, calculé à partir de la déclaration elle-même, avant toute analyse. Elle sert à savoir par quel dossier commencer. Ce n'est pas la priorité proposée par l'analyse : celle-ci n'existe qu'une fois l'analyse lancée, et elle peut être différente.",
    points: [
      doc("Urgence critique : une blessure est déclarée."),
      app(
        "Urgence haute : le devis dépasse 5 000 TND, ou le message du client a été signalé.",
      ),
      app(
        "Urgence basse : le montant est inférieur à 1 000 TND et aucun des points ci-dessus n'est présent.",
      ),
      app(
        "Urgence normale : tous les autres dossiers, y compris ceux dont le devis n'est pas encore renseigné.",
      ),
    ],
  },
];
