import { useEffect, useRef, useState } from "react";
import { streamChat } from "./api.js";
import Trace from "./Trace.jsx";

const EXAMPLES = [
  "What's the fair-use policy when roaming in the EU?",
  "How much data do I have left this month?",
  "I'm going to Japan for 10 days next month. What would roaming cost me on my current plan, in euros, and is there a cheaper option?",
  "My mobile data is really slow at home today, what's going on?",
];

export default function App() {
  // The frontend owns the conversation id; "New chat" simply starts a new one.
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const updateLast = (fn) => setMessages((ms) => [...ms.slice(0, -1), fn(ms[ms.length - 1])]);

  async function send(text) {
    const message = text.trim();
    if (!message || running) return;
    setInput("");
    setRunning(true);
    setMessages((ms) => [
      ...ms,
      { role: "user", text: message },
      { role: "assistant", text: "", steps: [], error: null },
    ]);
    await streamChat({
      threadId,
      message,
      onStep: (step) => updateLast((m) => ({ ...m, steps: [...m.steps, step] })),
      onAnswer: (answer) => updateLast((m) => ({ ...m, text: answer })),
      onError: (error) => updateLast((m) => ({ ...m, error })),
    });
    setRunning(false);
  }

  function newChat() {
    setThreadId(crypto.randomUUID());
    setMessages([]);
  }

  return (
    <div className="app">
      <header>
        <div>
          <h1>Martins Support</h1>
          <p className="muted">Logged in as Alex Demo (simulated) · fictional operator</p>
        </div>
        <button onClick={newChat} disabled={running}>New chat</button>
      </header>

      <main>
        {messages.length === 0 && (
          <div className="empty">
            <p>Ask about plans, roaming, billing, refunds or connectivity. Try:</p>
            {EXAMPLES.map((q) => (
              <button key={q} className="example" onClick={() => send(q)}>{q}</button>
            ))}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="msg user">{m.text}</div>
          ) : (
            <div key={i} className="msg assistant">
              {m.text && <div className="text">{m.text}</div>}
              {m.error && <div className="error">{m.error}</div>}
              {!m.text && !m.error && <div className="muted">Working…</div>}
              <Trace steps={m.steps} running={running && i === messages.length - 1} />
            </div>
          ),
        )}
        <div ref={bottomRef} />
      </main>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          placeholder={running ? "Waiting for the answer…" : "Type your question"}
          disabled={running}
          rows={2}
          maxLength={2000}
        />
        <button type="submit" disabled={running || !input.trim()}>Send</button>
      </form>
    </div>
  );
}
