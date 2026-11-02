export type Label = "BUY" | "NO_NEW_BUY" | "ABSTAIN";
export type Backend = "rules" | "hybrid" | "llm";
export type Origin = "post" | "parent" | "quoted";

export interface Asset {
  status: "SYMBOL" | "ADDRESS" | "UNRESOLVED";
  symbol: string | null;
  address: string | null;
  as_written: string | null;
  verified: false;
}

export interface Call {
  action: "BUY";
  asset: Asset;
  supporting_text: string;
  evidence_origin: Origin;
  explicitness: "explicit" | "implicit";
  conditional: boolean;
  condition_text: string | null;
}

export interface Decision {
  source: { source_id: string | null; platform: string; url: string | null; posted_at: string | null; is_manual_input: boolean };
  author: { status: "ATTRIBUTED" | "UNRESOLVED"; handle: string | null; platform_user_id: string | null };
  label: Label;
  calls: Call[];
  confidence: number;
  reasons: string[];
  limitations: string[];
  guard_corrections: string[];
  input_hash: string;
  versions: { policy: string; code: string; backend: string; model: string | null; prompt: string | null };
  cost: { usd: number; input_tokens: number; output_tokens: number; latency_ms: number; llm_calls: number; cache_hits: number };
}

export interface PostInput {
  source_id?: string | null;
  platform?: string;
  author?: { handle?: string | null } | null;
  text: string;
  context?: { kind?: string; parent_text?: string | null; quoted_text?: string | null };
}

export interface BatchResponse {
  decisions: Decision[];
  summary: { posts: number; labels: Record<Label, number>; llm_calls: number; cache_hits: number; usd_total: number; wall_seconds: number };
  evaluation: Evaluation | null;
}

export interface Evaluation {
  n: number;
  confusion_gold_x_predicted: Record<Label, Record<Label, number>>;
  buy: {
    correct: number;
    missed_as_no_new_buy: number;
    missed_as_abstain: number;
    false_buy: number;
    precision: number | null;
    precision_ci95: [number, number] | null;
    recall: number | null;
    recall_ci95: [number, number] | null;
  };
  abstention: { count: number; rate: number | null };
  accuracy_3way: number | null;
  attribution_errors_on_predicted_buy: Record<string, number>;
  decisions_with_guard_corrections: number;
}

export interface Health {
  status: string;
  code: string;
  policy: string;
  prompt: string;
  default_model: string;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => call<Health>("/api/health"),
  classifyText: (body: Record<string, unknown>) =>
    call<Decision>("/api/classify/text", { method: "POST", body: JSON.stringify(body) }),
  classifyBatch: (items: unknown[], backend: Backend) =>
    call<BatchResponse>("/api/classify/batch", { method: "POST", body: JSON.stringify({ items, backend }) }),
};

/** Accepts a JSON array, a single JSON object, or JSONL (one object per line). */
export function parseItems(raw: string): unknown[] {
  const text = raw.trim();
  if (!text) return [];
  if (text.startsWith("[")) return JSON.parse(text) as unknown[];
  try {
    return [JSON.parse(text)];
  } catch {
    return text
      .split("\n")
      .filter((line) => line.trim())
      .map((line, index) => {
        try {
          return JSON.parse(line);
        } catch {
          throw new Error(`Line ${index + 1} is not valid JSON.`);
        }
      });
  }
}
