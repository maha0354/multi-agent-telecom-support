import { useState } from "react";

const LLM_NODES = new Set(["router", "support", "analyst", "verifier", "responder"]);

function summarize(steps) {
  const path = steps.filter((s) => LLM_NODES.has(s.node)).map((s) => s.node);
  const route = steps.find((s) => s.node === "router" && !s.detail?.replan)?.detail?.category;
  const verdicts = steps.filter((s) => s.node === "verifier").flatMap((s) => s.detail?.verdicts ?? []);
  const toolCalls = steps.reduce((n, s) => n + (s.detail?.tool_calls?.length ?? 0), 0);
  const ms = steps.reduce((n, s) => n + (s.duration_ms ?? 0), 0);
  const highlights = [];
  if (steps.some((s) => s.node === "router" && s.detail?.replan)) highlights.push("re-plan");
  if (steps.some((s) => s.summary?.includes("(retry)"))) highlights.push("retry");
  if (steps.some((s) => s.node === "numbers_check" && s.summary?.includes("regenerate"))) highlights.push("reply regenerated");
  if (verdicts.some((v) => v.verdict === "dropped")) highlights.push("claim removed");
  return { path, route, verdicts, toolCalls, ms, highlights };
}

function StepDetail({ step }) {
  const d = step.detail ?? {};
  if (step.node === "router" && d.reason) return <p className="muted">{d.reason}</p>;
  if (step.node === "support" || step.node === "analyst") {
    return (
      <>
        {d.tool_calls?.length > 0 && (
          <ul className="tools">
            {d.tool_calls.map((c) => (
              <li key={c.evidence_id} className={c.error ? "bad" : ""}>
                <code>{c.evidence_id}</code> {c.tool}({Object.entries(c.args ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
                {c.error && " — error"}
              </li>
            ))}
          </ul>
        )}
        {d.claims?.length > 0 && (
          <ul className="claims">
            {d.claims.map((c) => (
              <li key={c.id}>
                {c.text} <span className="muted">[{c.evidence_ids.join(", ")}]</span>
              </li>
            ))}
          </ul>
        )}
        {d.evidence && Object.keys(d.evidence).length > 0 && (
          <details>
            <summary className="muted">Raw tool results</summary>
            <pre>{JSON.stringify(d.evidence, null, 2)}</pre>
          </details>
        )}
      </>
    );
  }
  if (step.node === "verifier") {
    return (
      <ul className="claims">
        {d.verdicts?.map((v) => (
          <li key={v.id + v.verdict} className={v.verdict === "pass" ? "good" : "bad"}>
            {v.verdict === "pass" ? "✓" : "✗"} {v.text}
            {v.verdict !== "pass" && <div className="muted">{v.reason}</div>}
          </li>
        ))}
      </ul>
    );
  }
  return null;
}

export default function Trace({ steps, running }) {
  const [open, setOpen] = useState(false);
  if (!steps.length) return null;
  const s = summarize(steps);
  const passed = s.verdicts.filter((v) => v.verdict === "pass").length;

  return (
    <div className="trace">
      <button className="trace-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span>{open ? "▾" : "▸"}</span>
        <span>
          {s.route && <b>{s.route}</b>} {s.path.join(" → ")}
          {s.verdicts.length > 0 && ` · ${passed}/${s.verdicts.length} claims verified`}
          {` · ${s.toolCalls} tool call${s.toolCalls === 1 ? "" : "s"}`}
          {` · ${(s.ms / 1000).toFixed(1)} s`}
          {running && " · working…"}
        </span>
        {s.highlights.map((h) => (
          <span key={h} className="badge">{h}</span>
        ))}
      </button>
      {open && (
        <ol className="steps">
          {steps.map((step, i) => (
            <li key={i}>
              <div className="step-head">
                <span className="node">{step.node}</span>
                <span>{step.summary}</span>
                <span className="muted">{step.duration_ms} ms</span>
              </div>
              <StepDetail step={step} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
