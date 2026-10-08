// POST /api/chat and read the server-sent events from the response body.
// EventSource only supports GET, so the stream is parsed by hand from fetch.

const CLIENT_TIMEOUT_MS = 180_000; // the backend gives up at 150 s; this is a last resort

export async function streamChat({ threadId, message, onStep, onAnswer, onError }) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CLIENT_TIMEOUT_MS);
  let finished = false;

  const handle = (event, data) => {
    if (event === "step") onStep(data);
    else if (event === "answer") onAnswer(data.answer);
    else if (event === "error") onError(data.message);
    else if (event === "done") finished = true;
  };

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, message }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Server responded ${response.status}`);

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      // Events are separated by a blank line.
      let boundary;
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
    onError(err.name === "AbortError" ? "No response in time. Please try again." : `Could not reach the assistant: ${err.message}`);
  } finally {
    clearTimeout(timer);
  }
}
