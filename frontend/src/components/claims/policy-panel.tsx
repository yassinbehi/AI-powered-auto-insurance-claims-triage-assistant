import { ChipList } from "@/components/status/chip-list";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { FORMULE_LABEL, formatDate, formatTnd } from "@/lib/status";
import type { Claim, Policy } from "@/lib/types";

function Ligne({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{children}</dd>
    </div>
  );
}

export function PolicyPanel({ policy }: { policy: Policy }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Police {policy.policy_id}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="space-y-2">
          <Ligne label="Assuré">{policy.assure}</Ligne>
          <Ligne label="Véhicule">{policy.vehicule}</Ligne>
          <Ligne label="Formule">{FORMULE_LABEL[policy.formule] ?? policy.formule}</Ligne>
          <Ligne label="Franchise">{formatTnd(policy.franchise_tnd)}</Ligne>
          <Ligne label="Couverture">
            {formatDate(policy.date_debut)} → {formatDate(policy.date_fin)}
          </Ligne>
        </dl>

        <Separator />

        <div className="space-y-1.5">
          <p className="text-xs font-medium">Garanties</p>
          <ChipList items={policy.garanties} emptyLabel="Aucune garantie listée" />
        </div>

        <div className="space-y-1.5">
          <p className="text-xs font-medium">Exclusions</p>
          <ChipList items={policy.exclusions} emptyLabel="Aucune exclusion" />
        </div>
      </CardContent>
    </Card>
  );
}

export function ClaimFactsPanel({ claim }: { claim: Claim }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Éléments déclarés</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="space-y-2">
          <Ligne label="Date du sinistre">{formatDate(claim.date_sinistre)}</Ligne>
          <Ligne label="Devis">{formatTnd(claim.devis_tnd)}</Ligne>
          <Ligne label="Constat">{claim.constat === "oui" ? "Oui" : "Non"}</Ligne>
          <Ligne label="Photos">{claim.photos === "oui" ? "Oui" : "Non"}</Ligne>
          <Ligne label="Tiers identifié">
            {claim.tiers_identifie === "oui" ? "Oui" : "Non"}
          </Ligne>
          <Ligne label="Blessure">{claim.blessure === "oui" ? "Oui" : "Non"}</Ligne>
          <Ligne label="Kilométrage">
            {new Intl.NumberFormat("fr-FR").format(claim.kilometrage_declare)} km
          </Ligne>
        </dl>
      </CardContent>
    </Card>
  );
}
