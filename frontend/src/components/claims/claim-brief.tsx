import { Camera, CircleSlash, FileCheck, HeartPulse, UserCheck } from "lucide-react";

import { DeclarationClient } from "@/components/claims/declaration-client";
import { StatusBadge } from "@/components/status/status-badge";
import { TYPE_SINISTRE_LABEL, FORMULE_LABEL, formatDate, formatTnd } from "@/lib/status";
import type { Claim, Policy, Screening } from "@/lib/types";

/**
 * De quoi parle ce dossier, avant de lire ce qu'il faut en faire.
 *
 * L'ecran d'analyse presentait jusqu'ici la prochaine action et le message au
 * client sans jamais dire de quel sinistre il s'agissait : le gestionnaire
 * devait revenir a la fiche dossier pour comprendre ce qu'il etait en train de
 * valider. On ne peut pas juger une prochaine action sans savoir ce qui s'est
 * passe, et un gestionnaire qui approuve sans comprendre est exactement ce que
 * la validation humaine est censee empecher.
 *
 * Ce composant ne rend QUE le contenu, sans cadre ni titre : c'est
 * TriageResultCard qui l'enveloppe dans un bloc, exactement comme "Prochaines
 * etapes" et "Message a envoyer au client". Une carte imbriquee dans une carte
 * en ferait un element a part, alors que c'est un element d'analyse comme les
 * autres.
 *
 * RIEN ICI N'EST REDIGE PAR LE MODELE. Tout est lu dans les fichiers deposes :
 * la phrase de tete est un gabarit rempli avec des faits, et le recit est
 * celui du client, tel quel. C'est delibere : le seul bloc dont le role est
 * d'ancrer le gestionnaire dans la realite du dossier est aussi le dernier
 * endroit ou l'on voudrait d'un texte invente. Le contenu est donc lu cote
 * serveur et ne coute rien, meme s'il s'affiche avec le resultat de l'analyse.
 */

/** Ce que le dossier contient, sous forme de badges lisibles d'un coup d'oeil.
 *  Presence ou absence de piece, pas jugement : c'est check_coverage et les
 *  regles qui disent si une piece manquante bloque, pas cet affichage. */
function Elements({ claim }: { claim: Claim }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <StatusBadge
        tone={claim.constat === "oui" ? "success" : "neutral"}
        icon={claim.constat === "oui" ? FileCheck : CircleSlash}
        label={claim.constat === "oui" ? "Constat fourni" : "Pas de constat"}
      />
      <StatusBadge
        tone={claim.photos === "oui" ? "success" : "neutral"}
        icon={claim.photos === "oui" ? Camera : CircleSlash}
        label={claim.photos === "oui" ? "Photos fournies" : "Pas de photos"}
      />
      <StatusBadge
        tone={claim.tiers_identifie === "oui" ? "success" : "neutral"}
        icon={claim.tiers_identifie === "oui" ? UserCheck : CircleSlash}
        label={claim.tiers_identifie === "oui" ? "Tiers identifié" : "Tiers non identifié"}
      />
      <StatusBadge
        tone={claim.blessure === "oui" ? "destructive" : "neutral"}
        icon={claim.blessure === "oui" ? HeartPulse : CircleSlash}
        label={claim.blessure === "oui" ? "Blessure déclarée" : "Aucune blessure"}
      />
    </div>
  );
}

export function ClaimBrief({
  claim,
  policy,
  screening,
}: {
  claim: Claim;
  policy: Policy;
  screening: Screening;
}) {
  const type = TYPE_SINISTRE_LABEL[claim.type_sinistre] ?? claim.type_sinistre;
  const formule = FORMULE_LABEL[policy.formule] ?? policy.formule;

  return (
    <div className="space-y-4">
      {/* GABARIT SANS ACCORD A DEVINER. Le type de sinistre et le vehicule
          viennent de fichiers deposes par l'utilisateur : on ne connait ni
          leur genre ni leur nombre. La phrase les introduit donc apres un
          mot dont l'accord est fixe ("un sinistre", "le vehicule"), ce qui
          reste correct pour "Renault Clio" comme pour "Camion Iveco". */}
      <p className="max-w-prose text-sm leading-relaxed">
        Un sinistre de type «&nbsp;{type}&nbsp;» a été déclaré le{" "}
        {formatDate(claim.date_sinistre)} par {policy.assure}. Le véhicule concerné est un{" "}
        {policy.vehicule}, assuré en formule {formule}.{" "}
        {claim.devis_tnd > 0
          ? `Le client présente un devis de ${formatTnd(claim.devis_tnd)}.`
          : "Aucun devis n'a encore été chiffré."}
      </p>

      <div className="max-w-prose space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground">Ce que le client raconte</p>
        <DeclarationClient screening={screening} />
      </div>

      <Elements claim={claim} />
    </div>
  );
}
