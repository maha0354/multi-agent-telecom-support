import { Sparkles } from "lucide-react";

const EXAMPLES = [
  "What's the fair-use policy when roaming in the EU?",
  "How much data do I have left this month?",
  "I'm going to Japan for 10 days next month. What would roaming cost me on my current plan, in euros, and is there a cheaper option?",
  "My mobile data is really slow at home today, what's going on?",
  "What's the cheapest way to use data in Brazil for a week?",
];

export default function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-10 text-center">
      <div>
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
          <Sparkles className="h-6 w-6" />
        </div>
        <h2 className="text-xl font-semibold tracking-tight">How can I help?</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Ask about plans, roaming, billing, refunds or connectivity. Try one of these:
        </p>
      </div>
      <div className="flex w-full max-w-xl flex-col gap-2">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="rounded-xl border border-border bg-card px-4 py-3 text-left text-sm text-foreground shadow-sm transition-all hover:border-primary/40 hover:shadow-md"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
