"use client";

import { Braces, Check, Copy } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

/** Le JSON exact du contrat de sortie, pour la demo et pour verification. */
export function RawJsonDialog({ value }: { value: unknown }) {
  const [copie, setCopie] = React.useState(false);
  const json = JSON.stringify(value, null, 2);

  async function copier() {
    await navigator.clipboard.writeText(json);
    setCopie(true);
    setTimeout(() => setCopie(false), 2000);
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Braces aria-hidden="true" />
          JSON
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Contrat de sortie</DialogTitle>
          <DialogDescription>
            La sortie du modèle, telle que validée par backend/src/schema.py.
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh] rounded-md border">
          <pre className="p-4 font-mono text-xs leading-relaxed">{json}</pre>
        </ScrollArea>

        <Button variant="outline" size="sm" onClick={copier} className="self-start">
          {copie ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copie ? "Copié" : "Copier"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
