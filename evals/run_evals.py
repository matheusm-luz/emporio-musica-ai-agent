"""Eval suite: runs every case in cases.json against a real model and checks deterministic
assertions — which tools were called, facts the reply must contain and claims it must not make.

    uv run python evals/run_evals.py --model ollama:gemma4:12b [--only a3_price_takamine]

Each case runs in a fresh thread with a frozen clock and in-memory persistence. Results are
written to evals/results/<model>.md (summary + full transcripts for failed cases).
"""

import argparse
import json
import re
import statistics
import sys
import time
import unicodedata
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from emporio_agent.agent import Reply, StoreAgent, tool_call_preview
from emporio_agent.config import STORE_TZ, load_settings
from emporio_agent.tickets import InMemoryTicketStore

EVALS_DIR = Path(__file__).parent
DEFAULT_NOW = "2026-11-25T10:00:00"  # Wednesday, store open


@dataclass
class CaseResult:
    case_id: str
    failures: list[str]
    seconds: float
    tools: list[str]
    transcript: list[tuple[str, Reply]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def normalize_text(text: str) -> str:
    """Some models write typographic characters (narrow no-break spaces, U+2011 non-breaking
    hyphens) — e.g. 'SU‑21S'. Normalise them so assertions test content, not typography."""
    text = unicodedata.normalize("NFKC", text)
    return text.translate({0x2010: "-", 0x2011: "-"})


def check(case: dict, replies: list[Reply]) -> list[str]:
    called = [c.name for r in replies for c in r.tool_calls]
    final = normalize_text(replies[-1].text)
    failures = []
    for expected in case.get("expect_tools", []):
        if not any(re.fullmatch(expected, name) for name in called):
            failures.append(f"tool not called: {expected}")
    for forbidden in case.get("forbid_tools", []):
        if forbidden in called:
            failures.append(f"forbidden tool called: {forbidden}")
    for pattern in case.get("must_include", []):
        if not re.search(pattern, final, re.IGNORECASE):
            failures.append(f"missing: /{pattern}/")
    for pattern in case.get("must_not_include", []):
        if re.search(pattern, final, re.IGNORECASE):
            failures.append(f"forbidden content: /{pattern}/")
    return failures


def run_case(agent: StoreAgent, case: dict) -> CaseResult:
    thread = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
    replies: list[Reply] = []
    transcript = []
    start = time.perf_counter()
    try:
        for turn in case["turns"]:
            reply = agent.reply(thread, turn, customer_phone=case.get("phone"))
            replies.append(reply)
            transcript.append((turn, reply))
        failures = check(case, replies)
    except Exception as exc:  # a crash is a failed case, not a crashed suite
        failures = [f"error: {type(exc).__name__}: {exc}"]
    seconds = time.perf_counter() - start
    tools = [c.name for r in replies for c in r.tool_calls]
    return CaseResult(case["id"], failures, seconds, tools, transcript)


def write_report(model: str, results: list[CaseResult], path: Path) -> None:
    passed = sum(r.passed for r in results)
    latencies = [r.seconds for r in results]
    lines = [
        f"# Eval results — `{model}`",
        "",
        f"Run: {datetime.now():%Y-%m-%d %H:%M} · cases: {len(results)} · "
        f"**passed: {passed}/{len(results)}** · median latency per case: "
        f"{statistics.median(latencies):.1f}s",
        "",
        "| Case | Result | Tools called | Time | Failures |",
        "|------|--------|--------------|------|----------|",
    ]
    for r in results:
        verdict = "✅" if r.passed else "❌"
        failures = "<br>".join(r.failures).replace("|", "\\|")
        lines.append(
            f"| {r.case_id} | {verdict} | {', '.join(r.tools) or '—'} | {r.seconds:.1f}s | "
            f"{failures} |"
        )
    for r in (r for r in results if not r.passed):
        lines += ["", f"## ❌ {r.case_id}", ""]
        for message, reply in r.transcript:
            lines.append(f"**Customer:** {message}  ")
            for call in reply.tool_calls:
                lines.append(f"`{tool_call_preview(call, 200)}`  ")
            lines.append(f"**Agent:** {reply.text}")
            lines.append("")
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="LLM_MODEL to evaluate (default: from .env)")
    parser.add_argument("--only", nargs="*", help="case ids to run")
    args = parser.parse_args()

    settings = load_settings()
    if args.model:
        settings = replace(settings, llm_model=args.model)
    cases = json.loads((EVALS_DIR / "cases.json").read_text(encoding="utf-8"))
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]

    agents: dict[str, StoreAgent] = {}  # one agent per frozen clock value
    results = []
    for case in cases:
        now = case.get("now", DEFAULT_NOW)
        if now not in agents:
            frozen = datetime.fromisoformat(now).replace(tzinfo=STORE_TZ)
            agents[now] = StoreAgent(
                replace(settings, agent_now=frozen), InMemorySaver(), InMemoryTicketStore()
            )
        result = run_case(agents[now], case)
        results.append(result)
        status = "PASS" if result.passed else "FAIL " + "; ".join(result.failures)
        print(f"{case['id']:<36} {result.seconds:6.1f}s  {status}", flush=True)

    slug = re.sub(r"[^a-z0-9.-]+", "_", settings.llm_model.lower())
    report = EVALS_DIR / "results" / f"{slug}.md"
    if not args.only:
        write_report(settings.llm_model, results, report)
        print(f"\nReport: {report}")
    passed = sum(r.passed for r in results)
    print(f"{settings.llm_model}: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
