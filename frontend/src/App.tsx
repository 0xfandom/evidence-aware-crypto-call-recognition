import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, parseItems } from "./api";
import type { Backend, BatchResponse, Decision, Health, Label, PostInput } from "./api";
import { CaseFile, LABEL_COLOR, formatMs } from "./CaseFile";
import type { PostTexts } from "./CaseFile";

type Kind = "original" | "reply" | "quote" | "repost";

interface Draft {
  text: string;
  source_id: string;
  author_handle: string;
  kind: Kind;
  parent_text: string;
  quoted_text: string;
}

const EMPTY: Draft = { text: "", source_id: "", author_handle: "", kind: "original", parent_text: "", quoted_text: "" };

const EXAMPLES: { name: string; slug: string; draft: Partial<Draft> }[] = [
  { name: "Explicit call", slug: "explicit", draft: { text: "Buying $SOL here. 140 is the line in the sand.", source_id: "x:1001", author_handle: "@alpha_rider" } },
  { name: "Implicit call", slug: "implicit", draft: { text: "$AVAX under 20 is a gift for anyone paying attention.", source_id: "x:1002", author_handle: "@chartmonk" } },
  { name: "Forecast only", slug: "forecast", draft: { text: "$BTC 150k by the end of 2027. Mark this post.", source_id: "x:1003", author_handle: "@satsmaxi_kai" } },
  { name: "Past call", slug: "past-call", draft: { text: "Told you all to buy $PEPE at 0.0000012. Who listened?", source_id: "x:1004", author_handle: "@degenlens" } },
  { name: "Sarcasm", slug: "sarcasm", draft: { text: "Sure, buy more $LUNA, what could possibly go wrong 🤡", source_id: "x:1005", author_handle: "@onchain_owl" } },
  { name: "Scam warning", slug: "scam-warning", draft: { text: "Honeypot alert on $GLOOM. You can buy it. You cannot sell it.", source_id: "tg:1006", author_handle: "@guard_dog" } },
  {
    name: "Reply with context",
    slug: "reply",
    draft: { text: "$TIA for sure", source_id: "x:1007", author_handle: "@chartmonk", kind: "reply", parent_text: "Which coin would you buy right now?" },
  },
  { name: "No source id", slug: "no-source", draft: { text: "Accumulating $ETH under 2,500.", source_id: "", author_handle: "" } },
];

const BACKENDS: { value: Backend; name: string; hint: string }[] = [
  { value: "rules", name: "Rules", hint: "Offline and free" },
  { value: "hybrid", name: "Hybrid", hint: "Rules can only rule a post out; Claude confirms every possible BUY" },
  { value: "llm", name: "Claude", hint: "Every post goes to Claude" },
];

const params = new URLSearchParams(window.location.search);
const initialBackend: Backend = BACKENDS.find((b) => b.value === params.get("backend"))?.value ?? "rules";

const field =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 " +
  "focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:focus:ring-slate-200";
const primary =
  "rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-40 " +
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 " +
  "dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white";

function Segmented<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: { value: T; name: string; hint?: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-slate-300 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          title={option.hint}
          onClick={() => onChange(option.value)}
          className={`rounded px-3 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 ${
            value === option.value
              ? "bg-slate-900 font-semibold text-white dark:bg-slate-100 dark:text-slate-900"
              : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
          }`}
        >
          {option.name}
        </button>
      ))}
    </div>
  );
}

function Labelled({ text, children }: { text: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-xs text-slate-500 dark:text-slate-400">
      {text}
      {children}
    </label>
  );
}

function ErrorText({ message }: { message: string }) {
  return <p role="alert" className="text-sm text-red-700 dark:text-red-400">{message}</p>;
}

function SinglePost({ backend }: { backend: Backend }) {
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [result, setResult] = useState<{ decision: Decision; post: PostTexts; roundTripMs: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (key: keyof Draft) => (event: { target: { value: string } }) => setDraft({ ...draft, [key]: event.target.value });

  async function classify(current: Draft = draft) {
    setBusy(true);
    setError(null);
    const started = performance.now();
    try {
      const decision = await api.classifyText({
        backend,
        text: current.text,
        source_id: current.source_id || null,
        author_handle: current.author_handle || null,
        kind: current.kind,
        parent_text: current.kind === "reply" ? current.parent_text || null : null,
        quoted_text: current.kind === "quote" || current.kind === "repost" ? current.quoted_text || null : null,
      });
      setResult({
        decision,
        post: {
          text: current.text,
          parent_text: current.kind === "reply" ? current.parent_text || null : null,
          quoted_text: current.kind === "quote" || current.kind === "repost" ? current.quoted_text || null : null,
        },
        roundTripMs: performance.now() - started,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function loadExample(slug: string, run: boolean) {
    const example = EXAMPLES.find((item) => item.slug === slug);
    if (!example) return;
    const loaded = { ...EMPTY, ...example.draft };
    setDraft(loaded);
    setResult(null);
    if (run) void classify(loaded);
  }

  // `/?example=sarcasm&backend=hybrid` opens an example and runs it, so demo links can be shared.
  useEffect(() => {
    const slug = params.get("example");
    if (slug) loadExample(slug, true);
  }, []);

  return (
    <div className="grid items-start gap-8 md:grid-cols-[minmax(18rem,24rem)_1fr]">
      <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); void classify(); }}>
        <select aria-label="Load an example" value="" onChange={(event) => loadExample(event.target.value, false)} className={field}>
          <option value="" disabled>Load an example</option>
          {EXAMPLES.map((example) => <option key={example.slug} value={example.slug}>{example.name}</option>)}
        </select>
        <textarea
          aria-label="Post text"
          rows={6}
          value={draft.text}
          onChange={set("text")}
          placeholder="Paste a post exactly as written"
          required
          className={`${field} resize-y font-serif text-base`}
        />
        <details className="rounded-md border border-slate-200 px-3 py-2 dark:border-slate-800">
          <summary className="cursor-pointer text-sm text-slate-600 dark:text-slate-400">Source, author and context</summary>
          <div className="mt-3 grid gap-3">
            <Labelled text="Source id">
              <input value={draft.source_id} onChange={set("source_id")} placeholder="Leave empty for pasted text" className={field} />
            </Labelled>
            <Labelled text="Author">
              <input value={draft.author_handle} onChange={set("author_handle")} placeholder="@handle" className={field} />
            </Labelled>
            <Labelled text="Post type">
              <select value={draft.kind} onChange={set("kind")} className={field}>
                <option value="original">Original post</option>
                <option value="reply">Reply</option>
                <option value="quote">Quote</option>
                <option value="repost">Repost</option>
              </select>
            </Labelled>
            {draft.kind === "reply" && (
              <Labelled text="Post being replied to">
                <textarea rows={2} value={draft.parent_text} onChange={set("parent_text")} className={field} />
              </Labelled>
            )}
            {(draft.kind === "quote" || draft.kind === "repost") && (
              <Labelled text="Quoted post">
                <textarea rows={2} value={draft.quoted_text} onChange={set("quoted_text")} className={field} />
              </Labelled>
            )}
          </div>
        </details>
        <button type="submit" disabled={busy || !draft.text.trim()} className={primary}>
          {busy ? "Classifying…" : "Classify"}
        </button>
        {error && <ErrorText message={error} />}
      </form>
      <div className="min-w-0">
        {result ? (
          <CaseFile decision={result.decision} post={result.post} roundTripMs={result.roundTripMs} />
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 p-8 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
            The decision appears here, with its evidence highlighted in the post.
          </p>
        )}
      </div>
    </div>
  );
}

/** Nearest-rank percentile: the smallest value with at least p of the values at or below it. */
function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length ? sorted[Math.max(0, Math.ceil(p * sorted.length) - 1)] : 0;
}

function postTexts(item: unknown): PostTexts {
  const record = item as { post?: PostInput } & PostInput;
  const post = record.post ?? record;
  return { text: post.text, parent_text: post.context?.parent_text ?? null, quoted_text: post.context?.quoted_text ?? null };
}

function goldOf(item: unknown): Label | null {
  return (item as { gold?: { label?: Label } }).gold?.label ?? null;
}

function BatchSummary({ result, roundTripMs }: { result: BatchResponse; roundTripMs: number }) {
  const { summary, evaluation } = result;
  const decide = result.decisions.filter((d) => d.cost.cache_hits === 0).map((d) => d.cost.latency_ms);
  const ci = (pair: [number, number] | null) => (pair ? ` (95% CI ${pair[0]}–${pair[1]})` : "");
  const rows: [string, ReactNode][] = evaluation
    ? [
        ["BUY recognised", evaluation.buy.correct],
        ["BUY missed", evaluation.buy.missed_as_no_new_buy + evaluation.buy.missed_as_abstain],
        ["Incorrect BUY", evaluation.buy.false_buy],
        ["Precision", `${evaluation.buy.precision ?? "n/a"}${ci(evaluation.buy.precision_ci95)}`],
        ["Recall", `${evaluation.buy.recall ?? "n/a"}${ci(evaluation.buy.recall_ci95)}`],
        ["Abstentions", evaluation.abstention.count],
        ["Attribution errors", Object.values(evaluation.attribution_errors_on_predicted_buy).reduce((a, b) => a + b, 0)],
      ]
    : [];
  return (
    <section className="space-y-2 text-sm">
      <p>
        {summary.posts} posts: {summary.labels.BUY} BUY, {summary.labels.NO_NEW_BUY} no new buy, {summary.labels.ABSTAIN} abstain.
        {" "}Claude calls {summary.llm_calls}, cache hits {summary.cache_hits}, cost ${summary.usd_total.toFixed(4)}.
      </p>
      <p>
        Latency: {formatMs(roundTripMs)} round trip for the batch
        {decide.length > 0 && (
          <>, {formatMs(decide.reduce((a, b) => a + b, 0) / decide.length)} per post on average, {formatMs(percentile(decide, 0.95))} at p95</>
        )}
        {summary.cache_hits > 0 && `, ${summary.cache_hits} answered from cache`}.
      </p>
      {evaluation && (
        <table className="mt-2 text-sm">
          <caption className="mb-1 text-left font-semibold">Against the gold labels</caption>
          <tbody>
            {rows.map(([name, value]) => (
              <tr key={name}>
                <th scope="row" className="py-0.5 pr-6 text-left font-normal text-slate-500 dark:text-slate-400">{name}</th>
                <td className="py-0.5">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Batch({ backend }: { backend: Backend }) {
  const [raw, setRaw] = useState("");
  const [items, setItems] = useState<unknown[]>([]);
  const [result, setResult] = useState<{ response: BatchResponse; roundTripMs: number } | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    setSelected(null);
    try {
      const parsed = parseItems(raw);
      if (!parsed.length) throw new Error("Paste or load at least one post.");
      setItems(parsed);
      const started = performance.now();
      const response = await api.classifyBatch(parsed, backend);
      setResult({ response, roundTripMs: performance.now() - started });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const toggle = (index: number) => setSelected(selected === index ? null : index);

  return (
    <div className="grid min-w-0 gap-6">
      <form className="grid max-w-3xl gap-3" onSubmit={(event) => { event.preventDefault(); void run(); }}>
        <textarea
          aria-label="Posts as JSON"
          rows={7}
          value={raw}
          onChange={(event) => setRaw(event.target.value)}
          placeholder={'JSON array or JSONL. Each item is a post, or {"post": ..., "gold": ...} to also get metrics.'}
          className={`${field} resize-y font-mono text-xs`}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <input
            type="file"
            aria-label="Load a JSON or JSONL file"
            accept=".json,.jsonl,application/json"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void file.text().then(setRaw);
            }}
            className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-200 file:px-3 file:py-1.5 file:text-sm dark:file:bg-slate-800 dark:file:text-slate-100"
          />
          <button type="submit" disabled={busy || !raw.trim()} className={primary}>
            {busy ? "Classifying…" : "Classify all"}
          </button>
        </div>
        {error && <ErrorText message={error} />}
      </form>

      {result && (
        <>
          <BatchSummary result={result.response} roundTripMs={result.roundTripMs} />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-300 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
                <tr>
                  <th scope="col" className="py-2 pr-4 font-medium">Source</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Decision</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Gold</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Asset</th>
                  <th scope="col" className="py-2 font-medium">Latency</th>
                </tr>
              </thead>
              <tbody>
                {result.response.decisions.map((decision, index) => {
                  const gold = goldOf(items[index]);
                  const mismatch = gold !== null && gold !== decision.label;
                  return (
                    <tr
                      key={index}
                      tabIndex={0}
                      onClick={() => toggle(index)}
                      onKeyDown={(event) => { if (event.key === "Enter") toggle(index); }}
                      className={`cursor-pointer border-b border-slate-200 hover:bg-white focus:outline-none focus-visible:bg-white dark:border-slate-800 dark:hover:bg-slate-900 ${
                        selected === index ? "bg-white dark:bg-slate-900" : ""
                      }`}
                    >
                      <td className="py-2 pr-4"><code className="text-xs">{decision.source.source_id ?? "missing"}</code></td>
                      <td className={`py-2 pr-4 font-semibold ${LABEL_COLOR[decision.label]}`}>{decision.label}</td>
                      <td className={`py-2 pr-4 ${mismatch ? "font-semibold text-red-700 dark:text-red-400" : ""}`}>{gold ?? ""}</td>
                      <td className="py-2 pr-4">{decision.calls.map((c) => c.asset.as_written ?? "unresolved").join(", ")}</td>
                      <td className="py-2 tabular-nums">{decision.cost.cache_hits ? "cached" : formatMs(decision.cost.latency_ms)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {selected !== null && <CaseFile decision={result.response.decisions[selected]} post={postTexts(items[selected])} />}
        </>
      )}
    </div>
  );
}

export function App() {
  const [tab, setTab] = useState<"single" | "batch">(params.get("mode") === "batch" ? "batch" : "single");
  const [backend, setBackend] = useState<Backend>(initialBackend);
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setOffline(true));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight sm:text-4xl">Evidence-Aware Crypto Call Recognition</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Is this post a genuine, current buy recommendation by its own author? Every decision shows its evidence.
          </p>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {offline ? "API not reachable. Start it with uv run eacr serve." : health ? `Connected, model ${health.default_model}` : "Connecting"}
        </p>
      </header>

      <div className="mt-8 flex flex-wrap items-center gap-3 border-b border-slate-200 pb-4 dark:border-slate-800">
        <Segmented
          label="Mode"
          value={tab}
          options={[{ value: "single" as const, name: "One post" }, { value: "batch" as const, name: "Many posts" }]}
          onChange={setTab}
        />
        <Segmented label="Classifier" value={backend} options={BACKENDS} onChange={setBackend} />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {BACKENDS.find((b) => b.value === backend)?.hint}
          {backend !== "rules" && ". Claude calls cost money; unchanged posts come from the cache for free."}
        </p>
      </div>

      <main className="mt-6">{tab === "single" ? <SinglePost backend={backend} /> : <Batch backend={backend} />}</main>
    </div>
  );
}
