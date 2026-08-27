"use client";

import * as React from "react";

import { triageStreamUrl } from "@/lib/api-client";
import { ajouterCout, formaterCout } from "@/lib/cumulative-cost";
import { devGroup, devLog, devWarn } from "@/lib/dev-log";
import type { ToolCall, TriageOutput, Usage } from "@/lib/types";

export type RunStatus = "idle" | "running" | "done" | "error" | "cancelled";

/** Une etape d'avancement, formulee en termes de dossier et non d'outils. */
export interface ProgressStep {
  key: string;
  label: string;
  done: boolean;
}

/**
 * Les 5 tools du backend, traduits en etapes comprehensibles. Le gestionnaire
 * n'a pas a savoir qu'il existe une fonction detect_fraud_signals.
 */
const ETAPE_PAR_OUTIL: Record<string, string> = {
  get_claim: "Lecture de la déclaration",
  get_policy: "Vérification du contrat",
  check_coverage: "Analyse de la couverture",
  estimate_repair_band: "Estimation du coût des réparations",
  detect_fraud_signals: "Contrôle des anomalies",
};

const ETAPE_REDACTION = "Rédaction de la réponse";

/**
 * Traduit un echec technique en phrase utile. Le message d'origine part dans
 * la console : "La reponse finale du modele n'est pas un JSON valide" ne dit
 * rien a un gestionnaire, et surtout ne lui dit pas quoi faire.
 */
function messageLisible(technique: string): string {
  if (technique.includes("JSON")) {
    return "L'analyse n'a pas pu être finalisée. Vous pouvez relancer le triage.";
  }
  if (technique.includes("Nombre maximal")) {
    return "L'analyse a été interrompue avant d'aboutir. Vous pouvez relancer le triage.";
  }
  if (technique.includes("Connexion")) {
    return "La connexion a été perdue pendant l'analyse. Vous pouvez relancer le triage.";
  }
  return "Le triage n'a pas abouti. Vous pouvez le relancer.";
}

interface State {
  status: RunStatus;
  steps: ProgressStep[];
  output: TriageOutput | null;
  error: string | null;
}

const ETAT_INITIAL: State = { status: "idle", steps: [], output: null, error: null };

type Action =
  | { kind: "start" }
  | { kind: "step_started"; key: string; label: string }
  | { kind: "step_done"; key: string }
  | { kind: "result"; output: TriageOutput | null }
  | { kind: "error"; message: string }
  | { kind: "transport_error"; message: string }
  | { kind: "done" }
  | { kind: "cancel" };

function reducer(state: State, action: Action): State {
  switch (action.kind) {
    case "start":
      return { ...ETAT_INITIAL, status: "running" };

    case "step_started": {
      if (state.steps.some((s) => s.key === action.key)) return state;
      return {
        ...state,
        steps: [...state.steps, { key: action.key, label: action.label, done: false }],
      };
    }

    case "step_done":
      return {
        ...state,
        steps: state.steps.map((s) => (s.key === action.key ? { ...s, done: true } : s)),
      };

    case "result":
      return {
        ...state,
        output: action.output,
        steps: state.steps.map((s) => ({ ...s, done: true })),
      };

    case "error":
      return { ...state, error: action.message, status: "error" };

    case "transport_error":
      // Une coupure apres la fin normale du flux n'est pas un incident.
      if (state.status !== "running") return state;
      return { ...state, error: action.message, status: "error" };

    case "done":
      return state.status === "running" ? { ...state, status: "done" } : state;

    case "cancel":
      return { ...state, status: "cancelled" };

    default:
      return state;
  }
}

/**
 * Suit un triage diffuse en SSE.
 *
 * L'ECRAN ne recoit que l'avancement en clair et le resultat final. Toute la
 * matiere technique - trace des outils, reponse brute du modele, tokens
 * consommes, ecarts de schema - part dans la console (lib/dev-log.ts).
 *
 * DEUX PIEGES DU TRANSPORT, traites ici :
 *
 * 1. EventSource se RECONNECTE tout seul quand le serveur ferme le flux. Sans
 *    fermeture explicite a la reception de `done`, chaque triage en
 *    relancerait un autre indefiniment - et chacun coute des appels de modele.
 *
 * 2. L'evenement applicatif s'appelle `run_error` et non `error`, parce que
 *    EventSource emet deja "error" pour ses pannes de transport. Les deux sont
 *    donc traites separement.
 */
export function useTriageStream(claimId: string) {
  const [state, dispatch] = React.useReducer(reducer, ETAT_INITIAL);
  const sourceRef = React.useRef<EventSource | null>(null);
  const texteRef = React.useRef("");

  const fermer = React.useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  const start = React.useCallback(
    (model?: string) => {
    if (sourceRef.current) return;

    texteRef.current = "";
    dispatch({ kind: "start" });
    devLog(`--- triage ${claimId}${model ? ` · ${model}` : ""} ---`);

    const source = new EventSource(triageStreamUrl(claimId, model));
    sourceRef.current = source;

    function surEvenement<T>(nom: string, gere: (donnees: T) => void) {
      source.addEventListener(nom, (event) => {
        gere(JSON.parse((event as MessageEvent).data) as T);
      });
    }

    surEvenement<{ turn: number; tool: string; input: Record<string, unknown> }>(
      "tool_use",
      (d) => {
        devLog(`tour ${d.turn} · ${d.tool}`, d.input);
        const label = ETAPE_PAR_OUTIL[d.tool];
        if (label) dispatch({ kind: "step_started", key: d.tool, label });
      },
    );

    surEvenement<{ turn: number; tool: string; output: Record<string, unknown> }>(
      "tool_result",
      (d) => {
        devGroup(`tour ${d.turn} · ${d.tool} → résultat`, d.output);
        dispatch({ kind: "step_done", key: d.tool });
      },
    );

    surEvenement<{ text: string }>("text_delta", (d) => {
      // Premier fragment : le modele a fini d'enqueter et redige.
      if (texteRef.current === "") {
        dispatch({ kind: "step_started", key: "redaction", label: ETAPE_REDACTION });
      }
      texteRef.current += d.text;
    });

    surEvenement<{ turn: number; usage: Usage }>("turn_completed", (d) =>
      devLog(`tour ${d.turn} terminé`, d.usage),
    );

    surEvenement<{
      output: TriageOutput | null;
      validation_errors: string[];
      tool_call_trace: ToolCall[];
      usage: Usage;
      cost_usd?: number;
    }>("result", (d) => {
      devGroup("réponse brute du modèle", texteRef.current);
      devGroup("trace des outils", d.tool_call_trace);
      devLog("consommation", d.usage);
      // Le detail par execution reste technique et part dans la console ; seul
      // le CUMUL est montre a l'ecran (composants layout/cumulative-cost-badge).
      devLog(`coût de l'analyse ${formaterCout(d.cost_usd ?? 0)}`);
      ajouterCout(d.cost_usd);
      if (d.validation_errors?.length) {
        // Ecarts au contrat de sortie : information de developpeur. Elle ne
        // change rien a ce que le gestionnaire doit faire du dossier.
        devWarn("écarts au contrat de sortie", d.validation_errors);
      }
      devGroup("sortie de triage", d.output);
      dispatch({ kind: "result", output: d.output });
    });

    surEvenement<{ message: string; raw_output?: string; cost_usd?: number }>(
      "run_error",
      (d) => {
        devWarn(d.message, d.raw_output);
        // Une analyse qui echoue en cours de route a deja consomme des appels
        // de modele : son cout compte dans le cumul comme celui d'une reussite.
        ajouterCout(d.cost_usd);
        dispatch({ kind: "error", message: messageLisible(d.message) });
      },
    );

    source.addEventListener("done", () => {
      dispatch({ kind: "done" });
      fermer(); // voir piege 1
    });

    source.onerror = () => {
      fermer();
      devWarn("flux SSE interrompu");
      dispatch({ kind: "transport_error", message: messageLisible("Connexion") });
    };
  }, [claimId, fermer]);

  const cancel = React.useCallback(() => {
    fermer();
    dispatch({ kind: "cancel" });
  }, [fermer]);

  React.useEffect(() => fermer, [fermer]);

  return { ...state, start, cancel };
}
