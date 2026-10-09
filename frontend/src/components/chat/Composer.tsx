import { useState } from "react";
import { SendHorizontal } from "lucide-react";

interface Props {
  running: boolean;
  onSend: (text: string) => void;
}

export default function Composer({ running, onSend }: Props) {
  const [input, setInput] = useState("");

  const submit = () => {
    const text = input.trim();
    if (!text || running) return;
    setInput("");
    onSend(text);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="border-t border-border bg-card px-4 py-3 sm:px-6"
    >
      <div className="flex items-end gap-2 rounded-2xl border border-input bg-background p-2 shadow-sm transition-colors focus-within:border-ring">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={running ? "Waiting for the answer…" : "Type your question"}
          disabled={running}
          rows={2}
          maxLength={2000}
          className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-foreground outline-none placeholder:text-muted-foreground disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={running || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-40"
          aria-label="Send message"
        >
          <SendHorizontal className="h-4 w-4" />
        </button>
      </div>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">
        Answers are verified against your account and the support knowledge base.
      </p>
    </form>
  );
}
