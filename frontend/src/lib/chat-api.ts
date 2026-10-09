// Client for the Martins Support FastAPI backend.
// POST /api/chat returns server-sent events; EventSource only supports GET,
// so the stream is parsed by hand from fetch.

export interface Customer {
  id: string;
  name: string;
  plan_name: string;
  area: string;
}

export interface ToolCall {
  evidence_id: string;
  tool: string;
  args?: Record<string, unknown>;
  error?: boolean;
}

export interface Claim {
  id: string;
  text: string;
  evidence_ids: string[];
}

export interface Verdict {
  id: string;
  verdict: "pass" | "dropped" | string;
  text: string;
  reason?: string;
}

export interface StepDetail {
  category?: string;
  reason?: string;
  replan?: boolean;
  tool_calls?: ToolCall[];
  claims?: Claim[];
  verdicts?: Verdict[];
  evidence?: Record<string, unknown>;
}

export interface ChatStep {
  node: string;
  summary?: string;
  duration_ms?: number;
  detail?: StepDetail;
}

export interface StreamHandlers {
  onStep: (step: ChatStep) => void;
  onAnswer: (answer: string) => void;
  onError: (message: string) => void;
}

const CLIENT_TIMEOUT_MS = 180_000; // the backend gives up at 150 s; this is a last resort

// Point at the running FastAPI backend, e.g. http://localhost:8000.
// Empty string = same origin (e.g. behind a dev proxy).
const BASE = (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "";

export async function fetchCustomers(): Promise<Customer[]> {
  const response = await fetch(`${BASE}/api/customers`);
  if (!response.ok) throw new Error(`Server responded ${response.status}`);
  return response.json();
}

export async function streamChat(
  params: { threadId: string; customerId: string; message: string } & StreamHandlers,
): Promise<void> {
  const { threadId, customerId, message, onStep, onAnswer, onError } = params;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CLIENT_TIMEOUT_MS);
  let finished = false;

  const handle = (event: string, data: Record<string, unknown>) => {
    if (event === "step") onStep(data as unknown as ChatStep);
    else if (event === "answer") onAnswer(data["answer"] as string);
    else if (event === "error") onError(data["message"] as string);
    else if (event === "done") finished = true;
  };

  try {
    const response = await fetch(`${BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, customer_id: customerId, message }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const detail = await response.json().then((b) => b.detail, () => null);
      throw new Error(
        typeof detail === "string" ? detail : `Server responded ${response.status}`,
      );
    }

    const reader = response.body!.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      // Events are separated by a blank line.
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = raw.match(/^event: (.*)$/m)?.[1];
        const data = raw.match(/^data: (.*)$/m)?.[1];
        if (event && data) handle(event, JSON.parse(data));
      }
    }
    if (!finished) onError("The connection closed before the answer was complete.");
  } catch (err) {
    const e = err as Error;
    onError(
      e.name === "AbortError"
        ? "No response in time. Please try again."
        : `Could not reach the assistant: ${e.message}`,
    );
  } finally {
    clearTimeout(timer);
  }
}
