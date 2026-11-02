import type { ReactNode } from "react";
import type { Call, Decision, Label, Origin } from "./api";

export interface PostTexts {
  text: string;
  parent_text?: string | null;
  quoted_text?: string | null;
}

const LABEL_TEXT: Record<Label, string> = {
  BUY: "Genuine current buy call",
  NO_NEW_BUY: "No new buy call",
  ABSTAIN: "Not enough evidence to decide",
};

export const LABEL_COLOR: Record<Label, string> = {
  BUY: "text-buy dark:text-buy-dark",
  NO_NEW_BUY: "text-slate-500 dark:text-slate-400",
  ABSTAIN: "text-abstain dark:text-abstain-dark",
};

export function formatMs(ms: number): string {
  if (ms < 1) return `${ms.toFixed(2)} ms`;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function assetName(call: Call): string {
  return call.asset.as_written ?? call.asset.symbol ?? call.asset.address ?? "unresolved";
}

function marked(text: string, calls: Call[], origin: Origin): ReactNode[] {
  const spans = calls
    .map((call, index) => ({ index, start: text.indexOf(call.supporting_text), call }))
    .filter((span) => span.call.evidence_origin === origin && span.start >= 0)
    .sort((a, b) => a.start - b.start);
  const nodes: ReactNode[] = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.start < cursor) continue;
    const end = span.start + span.call.supporting_text.length;
    nodes.push(
      text.slice(cursor, span.start),
      <mark key={span.index} className="rounded-sm bg-marker px-0.5 text-inherit dark:bg-marker-dark">
        {text.slice(span.start, end)}
      </mark>,
    );
    cursor = end;
  }
  nodes.push(text.slice(cursor));
  return nodes;
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-3 py-1.5">
      <dt className="text-sm text-slate-500 dark:text-slate-400">{term}</dt>
      <dd className="break-words text-sm">{children}</dd>
    </div>
  );
}

function Note({ children }: { children: ReactNode }) {
  return <span className="text-slate-500 dark:text-slate-400">{children}</span>;
}

function decidedBy(decision: Decision): string {
  const { backend, model } = decision.versions;
  const usedClaude = decision.cost.llm_calls > 0 || decision.cost.cache_hits > 0;
  const route = backend.startsWith("hybrid") ? "Hybrid, " : "";
  const name = usedClaude ? `Claude (${model})` : "rules";
  return `${route}${name}`;
}

export function CaseFile({ decision, post, roundTripMs }: { decision: Decision; post: PostTexts; roundTripMs?: number }) {
  const { source, author, calls, cost } = decision;
  const detailCount = decision.limitations.length + decision.guard_corrections.length;

  return (
    <article
      aria-live="polite"
      className="min-w-0 rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
    >
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className={`text-3xl font-bold tracking-tight ${LABEL_COLOR[decision.label]}`}>{decision.label}</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {LABEL_TEXT[decision.label]}, confidence {decision.confidence.toFixed(2)}
        </p>
      </header>

      <div className="mt-5 max-w-prose space-y-3 font-serif text-lg leading-relaxed">
        {post.parent_text && (
          <p className="border-l-2 border-slate-300 pl-3 text-base text-slate-500 dark:border-slate-700 dark:text-slate-400">
            Replying to: {marked(post.parent_text, calls, "parent")}
          </p>
        )}
        {post.quoted_text && (
          <p className="border-l-2 border-slate-300 pl-3 text-base text-slate-500 dark:border-slate-700 dark:text-slate-400">
            Quoting: {marked(post.quoted_text, calls, "quoted")}
          </p>
        )}
        <p className="whitespace-pre-wrap break-words">{marked(post.text, calls, "post")}</p>
      </div>

      <dl className="mt-5 divide-y divide-slate-100 border-t border-slate-100 dark:divide-slate-800 dark:border-slate-800">
        <Fact term="Source">
          {source.source_id ? <code className="text-[0.85em]">{source.source_id}</code> : "missing"}
          {source.is_manual_input && <Note> pasted by hand, not used for scoring</Note>}
        </Fact>
        <Fact term="Author">
          {author.status === "ATTRIBUTED" ? author.handle ?? author.platform_user_id : <Note>unresolved</Note>}
        </Fact>
        {calls.map((call, index) => (
          <Fact key={index} term={calls.length > 1 ? `Call ${index + 1}` : "Call"}>
            {call.explicitness === "explicit" ? "Explicit" : "Implicit"} buy of <strong>{assetName(call)}</strong>
            <Note> ({call.asset.status.toLowerCase()}, not verified)</Note>
            {call.conditional && call.condition_text && <Note> if: {call.condition_text}</Note>}
          </Fact>
        ))}
        <Fact term="Decided by">{decidedBy(decision)}</Fact>
        <Fact term="Latency">
          {cost.cache_hits > 0 ? "cached answer" : `${formatMs(cost.latency_ms)} to decide`}
          {roundTripMs !== undefined && `, ${formatMs(roundTripMs)} round trip`}
          {cost.usd > 0 && `, $${cost.usd.toFixed(4)}`}
        </Fact>
      </dl>

      <details className="mt-4 text-sm">
        <summary className="cursor-pointer text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200">
          Details{detailCount > 0 ? ` (${detailCount})` : ""}
        </summary>
        <div className="mt-3 space-y-3">
          {decision.limitations.length > 0 && (
            <section>
              <h3 className="font-semibold">Limitations</h3>
              <ul className="ml-5 list-disc">{decision.limitations.map((text) => <li key={text}>{text}</li>)}</ul>
            </section>
          )}
          {decision.guard_corrections.length > 0 && (
            <section>
              <h3 className="font-semibold text-abstain dark:text-abstain-dark">Changed by the evidence guard</h3>
              <ul className="ml-5 list-disc">{decision.guard_corrections.map((text) => <li key={text}>{text}</li>)}</ul>
            </section>
          )}
          <section>
            <h3 className="font-semibold">Reasons</h3>
            <p className="font-mono text-xs text-slate-500 dark:text-slate-400">{decision.reasons.join(", ") || "none"}</p>
          </section>
          <section>
            <h3 className="font-semibold">Raw decision</h3>
            <pre className="max-h-96 max-w-full overflow-auto whitespace-pre-wrap break-all rounded bg-slate-100 p-3 font-mono text-xs dark:bg-slate-950">
              {JSON.stringify(decision, null, 2)}
            </pre>
          </section>
        </div>
      </details>
    </article>
  );
}
