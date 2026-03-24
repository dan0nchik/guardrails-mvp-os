"""
Evaluate Runner — runs evaluation dataset WITH grounding pipeline enabled.

Usage:
    python -m benchmark.evaluate --provider openai --model gpt-4o
    python -m benchmark.evaluate --provider openai --model gpt-4.1-mini --domains medical

Results saved to benchmark/results/with_fgl_{model}_{date}.json
"""
import asyncio
import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///benchmark.db")
os.environ.setdefault("GUARDRAILS_BACKEND", "none")
os.environ.setdefault("DYNAMIC_RAILS_ENABLED", "false")
os.environ.setdefault("GROUNDING_ENABLED", "true")

DATASETS_DIR = Path(__file__).parent / "datasets"
RESULTS_DIR = Path(__file__).parent / "results"


def load_datasets(domains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Load evaluation datasets from JSON files."""
    all_questions = []
    files = {
        "medical": DATASETS_DIR / "medical.json",
        "financial": DATASETS_DIR / "financial.json",
        "general": DATASETS_DIR / "general.json",
    }
    for domain, filepath in files.items():
        if domains and domain not in domains:
            continue
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                questions = json.load(f)
                all_questions.extend(questions)
                print(f"  Loaded {len(questions)} questions from {domain}.json")
    return all_questions


async def run_single_question(runtime, question: Dict, idx: int, total: int) -> Dict[str, Any]:
    """Run a single question and collect grounding metrics."""
    qid = question["id"]
    text = question["question"]
    print(f"  [{idx + 1}/{total}] {qid}: {text[:60]}...")

    session_state = {"session_id": f"eval_{qid}"}
    trace_id = f"eval_trace_{qid}_{uuid.uuid4().hex[:8]}"

    start_time = time.time()
    try:
        result = await runtime.generate(
            user_message=text,
            session_state=session_state,
            agent_profile="evaluate",
            trace_id=trace_id,
            history=None,
        )
        latency_ms = (time.time() - start_time) * 1000
        error = None
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        result = {"message": "", "status": "error", "tool_calls": []}
        error = str(e)

    # Extract grounding results if available
    grounding_data = None
    gr = result.get("grounding_result")
    if gr is not None:
        grounding_data = {
            "claims_total": gr.claims_total,
            "claims_verified": gr.claims_verified,
            "claims_refuted": gr.claims_refuted,
            "claims_unverified": gr.claims_unverified,
            "claims_skipped": gr.claims_skipped,
            "sources_cited": gr.sources_cited,
            "disclaimers": gr.disclaimers,
            "pipeline_duration_ms": round(gr.pipeline_duration_ms, 2),
            "original_response": gr.original_response,
            "verdicts": [
                {
                    "claim_id": v.claim_id,
                    "claim_text": v.claim_text,
                    "status": v.status.value,
                    "confidence": v.confidence,
                    "reason": v.reason,
                    "evidence": {
                        "source_path": v.evidence.source_path,
                        "passage": v.evidence.passage[:200],
                        "relevance_score": v.evidence.relevance_score,
                        "nli_status": v.evidence.nli_status,
                        "nli_confidence": v.evidence.nli_confidence,
                    } if v.evidence else None,
                }
                for v in gr.verdicts
            ],
        }

    return {
        "id": qid,
        "domain": question["domain"],
        "question": text,
        "response": result.get("message", ""),
        "status": result.get("status", "error"),
        "tool_calls": result.get("tool_calls", []),
        "latency_ms": round(latency_ms, 2),
        "error": error,
        "expected_claims": question.get("expected_claims", []),
        "expected_tool_calls": question.get("expected_tool_calls", []),
        "risk_level": question.get("risk_level", "unknown"),
        "grounding": grounding_data,
    }


async def run_evaluate(
    provider: str,
    model: str,
    grounding_model: str = "",
    grounding_mode: str = "monitor",
    api_key: str = "",
    base_url: str = "",
    domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run evaluation with grounding enabled."""
    from app.config import settings

    settings.llm_provider = provider
    settings.llm_model = model
    if api_key:
        settings.llm_api_key = api_key
    settings.guardrails_backend = "none"
    settings.dynamic_rails_enabled = False
    settings.grounding_enabled = True
    settings.grounding_mode = grounding_mode
    if grounding_model:
        settings.grounding_model = grounding_model
    if base_url:
        settings.llm_base_url = base_url

    print(f"\n{'='*60}")
    print(f"Evaluate Runner (with Factual Grounding Layer)")
    print(f"  Provider:        {provider}")
    print(f"  Model:           {model}")
    print(f"  Grounding model: {grounding_model or model}")
    print(f"  Grounding mode:  {grounding_mode}")
    print(f"  Guardrails:      DISABLED")
    print(f"{'='*60}\n")

    print("Loading datasets...")
    questions = load_datasets(domains)
    print(f"Total questions: {len(questions)}\n")

    if not questions:
        print("No questions found.")
        return {}

    print("Initializing runtime (with grounding pipeline)...")
    from app.guardrails.runtime import GuardrailsRuntime
    runtime = GuardrailsRuntime()
    await runtime.initialize()
    print("Runtime initialized.\n")

    print("Running evaluation...")
    run_start = time.time()
    results = []
    for idx, question in enumerate(questions):
        result = await run_single_question(runtime, question, idx, len(questions))
        results.append(result)

    total_duration = time.time() - run_start

    successful = [r for r in results if r["status"] == "ok"]
    failed = [r for r in results if r["status"] in ("error", "escalated")]
    latencies = [r["latency_ms"] for r in successful]

    summary = {
        "total_questions": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "refused": len([r for r in results if r["status"] == "refused"]),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "p50_latency_ms": round(sorted(latencies)[len(latencies) // 2], 2) if latencies else 0,
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2) if latencies else 0,
        "total_duration_s": round(total_duration, 2),
        "by_domain": {},
    }

    domains_seen = set(r["domain"] for r in results)
    for domain in domains_seen:
        dr = [r for r in results if r["domain"] == domain]
        dl = [r["latency_ms"] for r in dr if r["status"] == "ok"]
        summary["by_domain"][domain] = {
            "total": len(dr),
            "successful": len([r for r in dr if r["status"] == "ok"]),
            "avg_latency_ms": round(sum(dl) / len(dl), 2) if dl else 0,
        }

    output = {
        "metadata": {
            "run_type": "with_fgl",
            "provider": provider,
            "model": model,
            "grounding_model": grounding_model or model,
            "grounding_mode": grounding_mode,
            "guardrails_enabled": False,
            "grounding_enabled": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "dataset_version": "v1",
        },
        "summary": summary,
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_safe = model.replace("/", "_").replace(":", "_")
    filename = f"with_fgl_{model_safe}_{date_str}.json"
    filepath = RESULTS_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY (with FGL)")
    print(f"{'='*60}")
    print(f"  Total:      {summary['total_questions']}")
    print(f"  Successful: {summary['successful']}")
    print(f"  Failed:     {summary['failed']}")
    print(f"  Avg latency:  {summary['avg_latency_ms']} ms")
    print(f"  P50 latency:  {summary['p50_latency_ms']} ms")
    print(f"  P95 latency:  {summary['p95_latency_ms']} ms")
    print(f"  Total time:   {summary['total_duration_s']} s")
    for domain, stats in summary["by_domain"].items():
        print(f"    {domain}: {stats['successful']}/{stats['total']} ok, avg {stats['avg_latency_ms']} ms")
    print(f"\n  Results saved to: {filepath}")
    print(f"{'='*60}\n")

    return output


def main():
    parser = argparse.ArgumentParser(description="Evaluate with Factual Grounding Layer")
    parser.add_argument("--provider", type=str, default="openai")
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument("--grounding-model", type=str, default="", help="Model for grounding (default: same as --model)")
    parser.add_argument("--grounding-mode", type=str, default="monitor", choices=["enforce", "monitor", "strict"])
    parser.add_argument("--api-key", type=str, default="")
    parser.add_argument("--base-url", type=str, default="")
    parser.add_argument("--domains", type=str, nargs="*", default=None)

    args = parser.parse_args()
    asyncio.run(run_evaluate(
        provider=args.provider,
        model=args.model,
        grounding_model=args.grounding_model,
        grounding_mode=args.grounding_mode,
        api_key=args.api_key,
        base_url=args.base_url,
        domains=args.domains,
    ))


if __name__ == "__main__":
    main()
