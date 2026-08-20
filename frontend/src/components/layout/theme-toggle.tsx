"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";

/**
 * Bascule clair / sombre.
 *
 * L'icone affichee est choisie en CSS, via la variante `dark:`, et non par un
 * etat React. C'est ce qui evite le classique drapeau "monte" pose dans un
 * effet : il provoque un rendu en cascade a chaque montage, et l'interface
 * n'apprend rien qu'une regle CSS ne sache deja.
 *
 * Le libelle accessible reste invariant pour la meme raison : il serait sinon
 * different entre le rendu serveur et le rendu client.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      aria-label="Changer de thème"
    >
      <Sun className="hidden dark:block" aria-hidden="true" />
      <Moon className="block dark:hidden" aria-hidden="true" />
    </Button>
  );
}
