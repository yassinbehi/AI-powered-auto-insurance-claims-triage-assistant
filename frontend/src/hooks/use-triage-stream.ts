"use client";

import * as React from "react";

import { triageStreamUrl } from "@/lib/api-client";
import type { ToolCall, TriageOutput, Usage } from "@/lib/types";

export type RunStatus = "idle" | "running" | "done" | "error" | "cancelled";

export interface TimelineToolCall {
  /** Identifiant local : un meme outil peut etre appele plusieurs fois. */
  key: string;
  tool: string;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
}

export interface TimelineTurn {
  turn: number;
  toolCalls: TimelineToolCall[];
  usage: Usage | null;
  completed: boolean;
}

export interface RunResult {
  output: TriageOutput | null;
  validation_errors: string[];
  tool_call_trace: ToolCall[];
  usage: Usage;
}

export interface RunError {
  message: string;
  rawOutput: string | null;
}

interface State {
  status: RunStatus;
  turns: TimelineTurn[];
  text: string;
  result: RunResult | null;
  error: RunError | null;
}

const ETAT_INITIAL: State = {
  status: "idle",
  turns: [],
  text: "",
  result: null,
  error: null,
};

type Action =
  | { kind: "start" }
  | { kind: "turn_started"; turn: number }
  | { kind: "turn_completed"; turn: number; usage: Usage }
  | { kind: "text_delta"; text: string }
  | { kind: "tool_use"; turn: number; tool: string; input: Record<string, unknown> }
  | { kind: "tool_result"; turn: number; tool: string; output: Record<string, unknown> }
  | { kind: "result"; result: RunResult }
  | { kind: "error"; error: RunError }
  | { kind: "transport_error"; error: RunError }
  | { kind: "done" }
  | { kind: "cancel" };

function majTour(
  turns: TimelineTurn[],
  numero: number,
  transforme: (turn: TimelineTurn) => TimelineTurn,
): TimelineTurn[] {
  const existe = turns.some((t) => t.turn === numero);
  const base = existe
    ? turns
    : [...turns, { turn: numero, toolCalls: [], usage: null, completed: false }];
  return base.map((t) => (t.turn === numero ? transforme(t) : t));
}

function reducer(state: State, action: Action): State {
  switch (action.kind) {
    case "start":
      return { ...ETAT_INITIAL, status: "running" };

    case "turn_started":
      return { ...state, turns: majTour(state.turns, action.turn, (t) => t) };

    case "turn_completed":
      return {
        ...state,
        turns: majTour(state.turns, action.turn, (t) => ({
          ...t,
          usage: action.usage,
          completed: true,
        })),
      };

    case "text_delta":
      return { ...state, text: state.text + action.text };

    case "tool_use":
      return {
        ...state,
        turns: majTour(state.turns, action.turn, (t) => ({
          ...t,
          toolCalls: [
            ...t.toolCalls,
            {
              key: `${action.turn}-${action.tool}-${t.toolCalls.length}`,
              tool: action.tool,
              input: action.input,
              output: null,
            },
          ],
        })),
      };

    case "tool_result": {
      // Le backend emet tool_use puis tool_result pour chaque bloc, dans
      // l'ordre : on complete donc le premier appel du meme outil encore sans
      // resultat.
      let complete = false;
      return {
        ...state,
        turns: majTour(state.turns, action.turn, (t) => ({
          ...t,
          toolCalls: t.toolCalls.map((call) => {
            if (complete || call.tool !== action.tool || call.output !== null) return call;
            complete = true;
            return { ...call, output: action.output };
          }),
        })),
      };
    }

    case "result":
      return { ...state, result: action.result };

    case "error":
      return { ...state, error: action.error, status: "error" };

    case "transport_error":
      // Une coupure apres la fin normale du flux n'est pas un incident : le
      // serveur ferme la connexion juste apres `done`, et EventSource le
      // signale comme une erreur. On n'alerte que si le triage etait encore
      // en cours.
      if (state.status !== "running") return state;
      return { ...state, error: action.error, status: "error" };

    case "done":
      // `done` arrive aussi apres une erreur : ne pas ecraser le statut.
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
 * DEUX POINTS QUI NE SONT PAS DES DETAILS :
 *
 * 1. EventSource se RECONNECTE tout seul quand le serveur ferme le flux. Sans
 *    fermeture explicite a la reception de `done`, chaque triage en relancerait
 *    un autre indefiniment - et chacun coute des appels de modele.
 *
 * 2. L'evenement applicatif s'appelle `run_error` et non `error`, parce que
 *    EventSource emet deja "error" pour ses pannes de transport. Les deux sont
 *    donc traites separement : l'un est un echec de triage, l'autre une
 *    connexion perdue.
 */
export function useTriageStream(claimId: string) {
  const [state, dispatch] = React.useReducer(reducer, ETAT_INITIAL);
  const sourceRef = React.useRef<EventSource | null>(null);

  const fermer = React.useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  const start = React.useCallback(() => {
    if (sourceRef.current) return;

    dispatch({ kind: "start" });
    const source = new EventSource(triageStreamUrl(claimId));
    sourceRef.current = source;

    function surEvenement<T>(nom: string, gere: (donnees: T) => void) {
      source.addEventListener(nom, (event) => {
        gere(JSON.parse((event as MessageEvent).data) as T);
      });
    }

    surEvenement<{ turn: number }>("turn_started", (d) =>
      dispatch({ kind: "turn_started", turn: d.turn }),
    );
    surEvenement<{ turn: number; usage: Usage }>("turn_completed", (d) =>
      dispatch({ kind: "turn_completed", turn: d.turn, usage: d.usage }),
    );
    surEvenement<{ text: string }>("text_delta", (d) =>
      dispatch({ kind: "text_delta", text: d.text }),
    );
    surEvenement<{ turn: number; tool: string; input: Record<string, unknown> }>(
      "tool_use",
      (d) => dispatch({ kind: "tool_use", turn: d.turn, tool: d.tool, input: d.input }),
    );
    surEvenement<{ turn: number; tool: string; output: Record<string, unknown> }>(
      "tool_result",
      (d) =>
        dispatch({ kind: "tool_result", turn: d.turn, tool: d.tool, output: d.output }),
    );
    surEvenement<RunResult>("result", (d) =>
      dispatch({
        kind: "result",
        result: {
          output: d.output,
          validation_errors: d.validation_errors ?? [],
          tool_call_trace: d.tool_call_trace ?? [],
          usage: d.usage ?? {},
        },
      }),
    );
    surEvenement<{ message: string; raw_output?: string }>("run_error", (d) =>
      dispatch({
        kind: "error",
        error: { message: d.message, rawOutput: d.raw_output ?? null },
      }),
    );

    source.addEventListener("done", () => {
      dispatch({ kind: "done" });
      fermer(); // voir point 1 de la docstring
    });

    source.onerror = () => {
      fermer();
      dispatch({
        kind: "transport_error",
        error: {
          message:
            "Connexion au flux de triage perdue. Vérifiez que l'API est toujours démarrée.",
          rawOutput: null,
        },
      });
    };
  }, [claimId, fermer]);

  const cancel = React.useCallback(() => {
    fermer();
    dispatch({ kind: "cancel" });
  }, [fermer]);

  // Ferme le flux si l'utilisateur quitte la page en cours de route.
  React.useEffect(() => fermer, [fermer]);

  return { ...state, start, cancel };
}
