"""
Baseline Runner — прогоняет evaluation dataset через текущий MVP (без grounding layer).

Использование:
    python -m benchmark.runner --provider openai --model gpt-4o
    python -m benchmark.runner --provider openai --model gpt-4o-mini
    python -m benchmark.runner --all  # прогнать все датасеты

Результаты сохраняются в benchmark/results/baseline_{model}_{date}.json
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

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set minimal required env vars before importing app modules
os.environ.setdefault("DATABASE_URL", "sqlite:///benchmark.db")
os.environ.setdefault("GUARDRAILS_BACKEND", "none")
os.environ.setdefault("DYNAMIC_RAILS_ENABLED", "false")


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


async def run_single_question(
    runtime,
    question: Dict[str, Any],
    question_idx: int,
    total: int,
) -> Dict[str, Any]:
    """Run a single question through the MVP pipeline and collect metrics."""
    qid = question["id"]
    text = question["question"]

    print(f"  [{question_idx + 1}/{total}] {qid}: {text[:60]}...")

    session_state = {"session_id": f"bench_{qid}"}
    trace_id = f"bench_trace_{qid}_{uuid.uuid4().hex[:8]}"

    # Measure latency
    start_time = time.time()

    try:
        result = await runtime.generate(
            user_message=text,
            session_state=session_state,
            agent_profile="benchmark",
            trace_id=trace_id,
            history=None,
        )
        latency_ms = (time.time() - start_time) * 1000
        status = "success"
        error = None
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        result = {
            "message": "",
            "status": "error",
            "tool_calls": [],
        }
        status = "error"
        error = str(e)

    return {
        "id": qid,
        "domain": question["domain"],
        "question": text,
        "response": result.get("message", ""),
        "status": result.get("status", status),
        "tool_calls": result.get("tool_calls", []),
        "latency_ms": round(latency_ms, 2),
        "error": error,
        "expected_claims": question.get("expected_claims", []),
        "expected_tool_calls": question.get("expected_tool_calls", []),
        "risk_level": question.get("risk_level", "unknown"),
    }


async def run_baseline(
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
    domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run the full baseline evaluation.

    Args:
        provider: LLM provider ('openai', 'anthropic', 'ollama', 'vllm')
        model: Model name (e.g. 'gpt-4o')
        api_key: API key override
        base_url: Custom base URL
        domains: List of domains to evaluate (None = all)

    Returns:
        Full results dictionary
    """
    from app.config import settings

    # Override settings for this run
    settings.llm_provider = provider
    settings.llm_model = model
    if api_key:
        settings.llm_api_key = api_key
    settings.guardrails_backend = "none"
    settings.dynamic_rails_enabled = False
    if base_url:
        settings.llm_base_url = base_url

    print(f"\n{'='*60}")
    print(f"Baseline Runner")
    print(f"  Provider: {provider}")
    print(f"  Model:    {model}")
    print(f"  Guardrails: DISABLED (baseline)")
    print(f"{'='*60}\n")

    # Load datasets
    print("Loading datasets...")
    questions = load_datasets(domains)
    print(f"Total questions: {len(questions)}\n")

    if not questions:
        print("No questions found. Check benchmark/datasets/ directory.")
        return {}

    # Initialize runtime
    print("Initializing runtime...")
    from app.guardrails.runtime import GuardrailsRuntime

    runtime = GuardrailsRuntime()
    await runtime.initialize()
    print("Runtime initialized.\n")

    # Run all questions
    print("Running evaluation...")
    run_start = time.time()
    results = []

    for idx, question in enumerate(questions):
        result = await run_single_question(runtime, question, idx, len(questions))
        results.append(result)

    total_duration = time.time() - run_start

    # Compute summary statistics
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
        "max_latency_ms": round(max(latencies), 2) if latencies else 0,
        "min_latency_ms": round(min(latencies), 2) if latencies else 0,
        "total_duration_s": round(total_duration, 2),
        "by_domain": {},
    }

    # Per-domain stats
    domains_seen = set(r["domain"] for r in results)
    for domain in domains_seen:
        domain_results = [r for r in results if r["domain"] == domain]
        domain_latencies = [r["latency_ms"] for r in domain_results if r["status"] != "error"]
        summary["by_domain"][domain] = {
            "total": len(domain_results),
            "successful": len([r for r in domain_results if r["status"] == "ok"]),
            "failed": len([r for r in domain_results if r["status"] in ("error", "escalated")]),
            "avg_latency_ms": round(sum(domain_latencies) / len(domain_latencies), 2) if domain_latencies else 0,
        }

    # Build output
    output = {
        "metadata": {
            "run_type": "baseline",
            "provider": provider,
            "model": model,
            "guardrails_enabled": False,
            "grounding_enabled": False,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "dataset_version": "v1",
        },
        "summary": summary,
        "results": results,
    }

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_safe = model.replace("/", "_").replace(":", "_")
    filename = f"baseline_{model_safe}_{date_str}.json"
    filepath = RESULTS_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Total:      {summary['total_questions']}")
    print(f"  Successful: {summary['successful']}")
    print(f"  Failed:     {summary['failed']}")
    print(f"  Refused:    {summary['refused']}")
    print(f"  Avg latency:  {summary['avg_latency_ms']} ms")
    print(f"  P50 latency:  {summary['p50_latency_ms']} ms")
    print(f"  P95 latency:  {summary['p95_latency_ms']} ms")
    print(f"  Total time:   {summary['total_duration_s']} s")
    print(f"\n  By domain:")
    for domain, stats in summary["by_domain"].items():
        print(f"    {domain}: {stats['successful']}/{stats['total']} ok, avg {stats['avg_latency_ms']} ms")
    print(f"\n  Results saved to: {filepath}")
    print(f"{'='*60}\n")

    return output


def main():
    parser = argparse.ArgumentParser(description="Baseline Runner for Evaluation Dataset")
    parser.add_argument("--provider", type=str, default="openai", help="LLM provider (default: openai)")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model name (default: gpt-4o)")
    parser.add_argument("--api-key", type=str, default="", help="API key (overrides env)")
    parser.add_argument("--base-url", type=str, default="", help="Custom base URL for provider")
    parser.add_argument("--domains", type=str, nargs="*", default=None,
                        help="Domains to evaluate (medical, financial, general). Default: all")
    parser.add_argument("--all", action="store_true", help="Run all domains (default behavior)")

    args = parser.parse_args()

    asyncio.run(run_baseline(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        domains=args.domains,
    ))


if __name__ == "__main__":
    main()
