import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  fetchCustomers,
  streamChat,
  type ChatStep,
  type Customer,
} from "@/lib/chat-api";
import { DEMO_CUSTOMERS, demoStreamChat } from "@/lib/chat-demo";
import ChatHeader from "@/components/chat/ChatHeader";
import EmptyState from "@/components/chat/EmptyState";
import Composer from "@/components/chat/Composer";
import Trace from "@/components/chat/Trace";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  steps: ChatStep[];
  error: string | null;
}

export default function App() {
  // The frontend owns the conversation id; "New chat" simply starts a new one.
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [running, setRunning] = useState(false);
  // Simulated login: the selected demo customer is sent with every message.
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchCustomers()
      .then((list) => {
        setCustomers(list);
        setCustomerId(list[0]?.id ?? "");
      })
      .catch(() => {
        // Backend unreachable: fall back to demo mode so the UI is explorable.
        setDemoMode(true);
        setCustomers(DEMO_CUSTOMERS);
        setCustomerId(DEMO_CUSTOMERS[0]?.id ?? "");
        setLoadError(null);
      });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const updateLast = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((ms) => {
      const last = ms[ms.length - 1];
      return last ? [...ms.slice(0, -1), fn(last)] : ms;
    });

  async function send(text: string) {
    const message = text.trim();
    if (!message || running || !customerId) return;
    setRunning(true);
    setMessages((ms) => [
      ...ms,
      { role: "user", text: message, steps: [], error: null },
      { role: "assistant", text: "", steps: [], error: null },
    ]);
    const handlers = {
      onStep: (step: ChatStep) =>
        updateLast((m) => ({ ...m, steps: [...m.steps, step] })),
      onAnswer: (answer: string) => updateLast((m) => ({ ...m, text: answer })),
      onError: (error: string) => updateLast((m) => ({ ...m, error })),
    };
    if (demoMode) {
      await demoStreamChat(handlers);
    } else {
      await streamChat({ threadId, customerId, message, ...handlers });
    }
    setRunning(false);
  }

  function newChat() {
    setThreadId(crypto.randomUUID());
    setMessages([]);
  }

  // A conversation belongs to one customer, so switching customer starts a new chat.
  function switchCustomer(id: string) {
    setCustomerId(id);
    newChat();
  }

  const customer = customers.find((c) => c.id === customerId);

  return (
    <div className="flex h-dvh flex-col bg-background">
      <ChatHeader
        customers={customers}
        customerId={customerId}
        customer={customer}
        loadError={loadError}
        running={running}
        demoMode={demoMode}
        onSwitchCustomer={switchCustomer}
        onNewChat={newChat}
      />

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col overflow-y-auto px-4 py-6 sm:px-6">
        {messages.length === 0 ? (
          <EmptyState onPick={send} />
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div
                  key={i}
                  className="max-w-[85%] self-end rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap text-primary-foreground shadow-sm"
                >
                  {m.text}
                </div>
              ) : (
                <div
                  key={i}
                  className="w-full max-w-[92%] self-start rounded-2xl rounded-bl-md border border-border bg-card px-4 py-3 shadow-sm"
                >
                  {m.text && (
                    <div className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">
                      {m.text}
                    </div>
                  )}
                  {m.error && <div className="text-sm text-destructive">{m.error}</div>}
                  {!m.text && !m.error && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Working…
                    </div>
                  )}
                  <Trace steps={m.steps} running={running && i === messages.length - 1} />
                </div>
              ),
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      <div className="mx-auto w-full max-w-3xl">
        <Composer running={running} onSend={send} />
      </div>
    </div>
  );
}
