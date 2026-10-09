import { MessageSquareText, Plus } from "lucide-react";
import type { Customer } from "@/lib/chat-api";

interface Props {
  customers: Customer[];
  customerId: string;
  customer: Customer | undefined;
  loadError: string | null;
  running: boolean;
  demoMode: boolean;
  onSwitchCustomer: (id: string) => void;
  onNewChat: () => void;
}

export default function ChatHeader({
  customers,
  customerId,
  customer,
  loadError,
  running,
  demoMode,
  onSwitchCustomer,
  onNewChat,
}: Props) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-3 sm:px-6">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <MessageSquareText className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-base font-semibold tracking-tight">Martins Support</h1>
          <p className="text-xs text-muted-foreground">
            {customer
              ? `${customer.name} · ${customer.plan_name} · ${customer.area}${demoMode ? " · demo" : " (simulated login)"}`
              : (loadError ?? "Loading customers…")}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <label>
          <span className="sr-only">Simulated customer</span>
          <select
            value={customerId}
            onChange={(e) => onSwitchCustomer(e.target.value)}
            disabled={running || !customers.length}
            className="h-9 rounded-lg border border-input bg-card px-2.5 text-sm text-foreground shadow-sm outline-none transition-colors focus:border-ring disabled:opacity-50"
          >
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} — {c.plan_name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={onNewChat}
          disabled={running}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-input bg-card px-3 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-secondary disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          New chat
        </button>
      </div>
    </header>
  );
}
