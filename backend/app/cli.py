"""Run questions through the graph from the terminal and print the trace.

uv run python -m app.cli [-v] [--customer C-1003] "Which zone is Japan in?" ["follow-up" ...]
Questions given together share one conversation thread.
"""

import argparse
import time
import uuid

from langchain_core.messages import HumanMessage

from app.config import DEFAULT_CUSTOMER_ID
from app.graph import RECURSION_LIMIT, build_graph


def ask(graph, thread_id: str, customer_id: str, question: str, verbose: bool = False) -> str:
    print(f"\n>>> {question}")
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    start = time.perf_counter()
    answer = ""
    inputs = {"messages": [HumanMessage(question)], "customer_id": customer_id}
    for update in graph.stream(inputs, config, stream_mode="updates"):
        for node, values in update.items():
            step = (values or {}).get("step", {})
            print(f"  [{step.get('duration_ms', 0):>6} ms] {step.get('summary', node)}")
            if verbose and node == "verifier":
                for v in step["detail"]["verdicts"]:
                    print(f"      {v['verdict']:7} {v['text']}" + (f"  ({v['reason']})" if v["verdict"] != "pass" else ""))
            answer = (values or {}).get("answer") or answer
    print(f"  total {time.perf_counter() - start:.1f} s\n\n{answer}")
    return answer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("questions", nargs="+")
    parser.add_argument("-v", "--verbose", action="store_true", help="print verifier verdicts")
    parser.add_argument("--customer", default=DEFAULT_CUSTOMER_ID, help="simulated logged-in customer")
    args = parser.parse_args()
    graph = build_graph()
    thread = str(uuid.uuid4())
    for q in args.questions:
        ask(graph, thread, args.customer, q, args.verbose)
