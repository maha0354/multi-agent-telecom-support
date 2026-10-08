"""Run questions through the graph from the terminal and print the trace.

uv run python -m app.cli "Which zone is Japan in?" ["follow-up" ...]
Questions given together share one conversation thread.
"""

import sys
import time
import uuid

from langchain_core.messages import HumanMessage

from app.graph import RECURSION_LIMIT, build_graph


def ask(graph, thread_id: str, question: str, verbose: bool = False) -> str:
    print(f"\n>>> {question}")
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    start = time.perf_counter()
    answer = ""
    for update in graph.stream({"messages": [HumanMessage(question)]}, config, stream_mode="updates"):
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
    graph = build_graph()
    thread = str(uuid.uuid4())
    verbose = "-v" in sys.argv
    for q in [a for a in sys.argv[1:] if a != "-v"]:
        ask(graph, thread, q, verbose)
