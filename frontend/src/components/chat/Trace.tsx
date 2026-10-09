import { useState } from "react";
import { Check, ChevronDown, ChevronRight, X } from "lucide-react";
import type { ChatStep, StepDetail } from "@/lib/chat-api";

const LLM_NODES = new Set(["router", "support", "analyst", "verifier", "responder"]);

function summarize(steps: ChatStep[]) {
  const path = steps.filter((s) => LLM_NODES.has(s.node)).map((s) => s.node);
  const route = steps.find((s) => s.node === "router" && !s.detail?.replan)?.detail?.category;
  const verdicts = steps
    .filter((s) => s.node === "verifier")
    .flatMap((s) => s.detail?.verdicts ?? []);
  const toolCalls = steps.reduce((n, s) => n + (s.detail?.tool_calls?.length ?? 0), 0);
  const ms = steps.reduce((n, s) => n + (s.duration_ms ?? 0), 0);
  const highlights: string[] = [];
  if (steps.some((s) => s.node === "router" && s.detail?.replan)) highlights.push("re-plan");
  if (steps.some((s) => s.summary?.includes("(retry)"))) highlights.push("retry");
  if (steps.some((s) => s.node === "numbers_check" && s.summary?.includes("regenerate")))
    highlights.push("reply regenerated");
  if (verdicts.some((v) => v.verdict === "dropped")) highlights.push("claim removed");
  return { path, route, verdicts, toolCalls, ms, highlights };
}

function StepDetailView({ step }: { step: ChatStep }) {
  const d: StepDetail = step.detail ?? {};
  if (step.node === "router" && d.reason) {
    return <p className="mt-1 text-xs text-muted-foreground">{d.reason}</p>;
  }
  if (step.node === "support" || step.node === "analyst") {
    return (
      <div className="mt-1.5 space-y-2">
        {d.tool_calls && d.tool_calls.length > 0 && (
          <ul className="space-y-1">
            {d.tool_calls.map((c) => (
              <li
                key={c.evidence_id}
                className={`font-mono text-[11px] ${c.error ? "text-destructive" : "text-muted-foreground"}`}
              >
                <span className="mr-1.5 inline-block rounded bg-secondary px-1.5 py-0.5 font-semibold text-secondary-foreground">
                  {c.evidence_id}
                </span>
                {c.tool}(
                {Object.entries(c.args ?? {})
                  .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                  .join(", ")}
                ){c.error && " — error"}
              </li>
            ))}
          </ul>
        )}
        {d.claims && d.claims.length > 0 && (
          <ul className="space-y-1">
            {d.claims.map((c) => (
              <li key={c.id} className="text-xs text-foreground">
                {c.text}{" "}
                <span className="text-muted-foreground">[{c.evidence_ids.join(", ")}]</span>
              </li>
            ))}
          </ul>
        )}
        {d.evidence && Object.keys(d.evidence).length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              Raw tool results
            </summary>
            <pre className="mt-1 max-h-60 overflow-auto rounded-lg bg-secondary p-2.5 font-mono text-[11px] whitespace-pre-wrap break-words text-secondary-foreground">
              {JSON.stringify(d.evidence, null, 2)}
            </pre>
          </details>
        )}
      </div>
    );
  }
  if (step.node === "verifier") {
    return (
      <ul className="mt-1.5 space-y-1">
        {d.verdicts?.map((v) => (
          <li key={v.id + v.verdict} className="flex items-start gap-1.5 text-xs">
            {v.verdict === "pass" ? (
              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
            ) : (
              <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
            )}
            <span className={v.verdict === "pass" ? "text-foreground" : "text-destructive"}>
              {v.text}
              {v.verdict !== "pass" && v.reason && (
                <span className="block text-muted-foreground">{v.reason}</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    );
  }
  return null;
}

export default function Trace({ steps, running }: { steps: ChatStep[]; running: boolean }) {
  const [open, setOpen] = useState(false);
  if (!steps.length) return null;
  const s = summarize(steps);
  const passed = s.verdicts.filter((v) => v.verdict === "pass").length;

  return (
    <div className="mt-3 border-t border-border pt-2.5">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-2 gap-y-1 text-left text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0" />
        )}
        <span>
          {s.route && <b className="mr-1 font-semibold text-foreground">{s.route}</b>}
          {s.path.join(" → ")}
          {s.verdicts.length > 0 && ` · ${passed}/${s.verdicts.length} claims verified`}
          {` · ${s.toolCalls} tool call${s.toolCalls === 1 ? "" : "s"}`}
          {` · ${(s.ms / 1000).toFixed(1)} s`}
          {running && " · working…"}
        </span>
        {s.highlights.map((h) => (
          <span
            key={h}
            className="rounded-full bg-warning/20 px-2 py-0.5 text-[10px] font-semibold text-foreground"
          >
            {h}
          </span>
        ))}
      </button>
      {open && (
        <ol className="mt-2.5 space-y-3 border-l-2 border-border pl-4">
          {steps.map((step, i) => (
            <li key={i}>
              <div className="flex flex-wrap items-baseline gap-x-2 text-xs">
                <span className="font-semibold text-foreground">{step.node}</span>
                <span className="text-muted-foreground">{step.summary}</span>
                <span className="text-[10px] text-muted-foreground/70">
                  {step.duration_ms} ms
                </span>
              </div>
              <StepDetailView step={step} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
