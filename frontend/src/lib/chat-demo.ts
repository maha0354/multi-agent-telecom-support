// Demo mode: used when the Python backend is unreachable, so the redesigned
// UI can be explored with simulated customers and a scripted streaming answer.

import type { ChatStep, Customer, StreamHandlers } from "./chat-api";

export const DEMO_CUSTOMERS: Customer[] = [
  { id: "C-1001", name: "Alex Demo", plan_name: "Plus 30 GB", area: "Uppsala" },
  { id: "C-1002", name: "Sara Demo", plan_name: "Bas 10 GB", area: "Malmö" },
  { id: "C-1003", name: "Johan Demo", plan_name: "World 150 GB", area: "Stockholm" },
  { id: "C-1004", name: "Lina Demo", plan_name: "Max 100 GB", area: "Kiruna" },
  { id: "C-1005", name: "Omar Demo", plan_name: "Bas 10 GB", area: "Göteborg" },
];

const DEMO_STEPS: ChatStep[] = [
  {
    node: "router",
    summary: 'Category "both", plan: support → analyst',
    duration_ms: 1820,
    detail: {
      category: "both",
      reason:
        "The question needs policy info (roaming zone) and account data (plan, prices), so both agents run.",
    },
  },
  {
    node: "support",
    summary: "Found the roaming zone in the knowledge base",
    duration_ms: 4310,
    detail: {
      tool_calls: [
        {
          evidence_id: "E1",
          tool: "search_support_docs",
          args: { query: "Japan roaming zone" },
        },
      ],
      claims: [
        { id: "C1", text: "Japan is in Roaming Zone 4 (Asia-Pacific).", evidence_ids: ["E1"] },
      ],
      evidence: {
        E1: "Roaming > Zone 4: Asia-Pacific — Japan, South Korea, Thailand… 89 SEK/GB pay-as-you-go.",
      },
    },
  },
  {
    node: "analyst",
    summary: "Compared trip costs on the current plan",
    duration_ms: 6890,
    detail: {
      tool_calls: [
        { evidence_id: "E2", tool: "get_my_account", args: {} },
        {
          evidence_id: "E3",
          tool: "compare_roaming_options",
          args: { zone: 4, days: 10 },
        },
        { evidence_id: "E4", tool: "convert_currency", args: { amount: 774, to: "EUR" } },
      ],
      claims: [
        { id: "C2", text: "Pay-as-you-go for 10 days in Japan costs about 774 SEK.", evidence_ids: ["E2", "E3"] },
        { id: "C3", text: "Upgrading to World for one month (+300 SEK) is the cheapest option.", evidence_ids: ["E3"] },
      ],
      evidence: {
        E3: "Options sorted by cost: 1) Upgrade to World +300 SEK (cheapest) 2) 7-day Travel Pass + 3 days PAYG 549 SEK 3) Pay-as-you-go 774 SEK.",
      },
    },
  },
  {
    node: "verifier",
    summary: "3 of 3 claims verified",
    duration_ms: 2140,
    detail: {
      verdicts: [
        { id: "C1", verdict: "pass", text: "Japan is in Roaming Zone 4 (Asia-Pacific)." },
        { id: "C2", verdict: "pass", text: "Pay-as-you-go for 10 days in Japan costs about 774 SEK." },
        { id: "C3", verdict: "pass", text: "Upgrading to World for one month (+300 SEK) is the cheapest option." },
      ],
    },
  },
  {
    node: "responder",
    summary: "Reply written from verified claims",
    duration_ms: 1980,
  },
];

const DEMO_ANSWER = `For a 10-day trip to Japan on your current plan, here's how the options compare:

• Pay-as-you-go: about 774 SEK (≈ 67 EUR) at the Zone 4 rate of 89 SEK/GB.
• Travel Pass: a 7-day pass plus 3 pay-as-you-go days comes to about 549 SEK.
• Plan upgrade: switching to World for one month costs +300 SEK and includes Zone 4 — this is the cheapest option, and you can downgrade after the trip.

So the cheapest way is the one-month World upgrade at +300 SEK.`;

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function demoStreamChat(handlers: StreamHandlers): Promise<void> {
  for (const step of DEMO_STEPS) {
    await wait(500 + Math.random() * 400);
    handlers.onStep(step);
  }
  await wait(400);
  handlers.onAnswer(DEMO_ANSWER);
}
