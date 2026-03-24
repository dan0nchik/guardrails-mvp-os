"""
Compare — compares baseline vs with-FGL evaluation results.

Usage:
    python -m benchmark.compare --baseline results/baseline_*.json --fgl results/with_fgl_*.json
    python -m benchmark.compare --auto  # auto-find latest results
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

RESULTS_DIR = Path(__file__).parent / "results"


def find_latest_result(prefix: str) -> Optional[Path]:
    """Find the most recent result file with given prefix."""
    files = sorted(RESULTS_DIR.glob(f"{prefix}*.json"), reverse=True)
    return files[0] if files else None


def load_result(filepath: Path) -> Dict:
    """Load a result JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_claim_metrics(results: List[Dict]) -> Dict:
    """Compute claim-level metrics from evaluation results."""
    total_expected_claims = 0
    total_responses = len(results)
    responses_with_content = 0

    for r in results:
        expected = r.get("expected_claims", [])
        total_expected_claims += len(expected)
        if r.get("response") and r["status"] == "ok":
            responses_with_content += 1

    return {
        "total_responses": total_responses,
        "responses_with_content": responses_with_content,
        "total_expected_claims": total_expected_claims,
        "response_rate": round(responses_with_content / total_responses * 100, 1) if total_responses else 0,
    }


def compare(baseline_path: Path, fgl_path: Path):
    """Compare baseline and FGL results."""
    baseline = load_result(baseline_path)
    fgl = load_result(fgl_path)

    b_meta = baseline["metadata"]
    f_meta = fgl["metadata"]
    b_summary = baseline["summary"]
    f_summary = fgl["summary"]

    print(f"\n{'='*70}")
    print(f"COMPARISON: Baseline vs With Factual Grounding Layer")
    print(f"{'='*70}")
    print(f"  Baseline: {baseline_path.name}")
    print(f"    Model: {b_meta['model']}, Provider: {b_meta['provider']}")
    print(f"  FGL:      {fgl_path.name}")
    print(f"    Model: {f_meta['model']}, Grounding model: {f_meta.get('grounding_model', 'N/A')}")
    print(f"    Mode: {f_meta.get('grounding_mode', 'N/A')}")
    print(f"{'='*70}\n")

    # Summary comparison table
    print(f"{'Metric':<30} {'Baseline':>12} {'+ FGL':>12} {'Delta':>12}")
    print(f"{'-'*66}")

    metrics = [
        ("Total questions", b_summary["total_questions"], f_summary["total_questions"]),
        ("Successful", b_summary["successful"], f_summary["successful"]),
        ("Failed", b_summary["failed"], f_summary["failed"]),
        ("Refused", b_summary.get("refused", 0), f_summary.get("refused", 0)),
        ("Avg latency (ms)", b_summary["avg_latency_ms"], f_summary["avg_latency_ms"]),
        ("P50 latency (ms)", b_summary["p50_latency_ms"], f_summary["p50_latency_ms"]),
        ("P95 latency (ms)", b_summary.get("p95_latency_ms", 0), f_summary.get("p95_latency_ms", 0)),
        ("Total time (s)", b_summary["total_duration_s"], f_summary["total_duration_s"]),
    ]

    for name, b_val, f_val in metrics:
        delta = f_val - b_val
        sign = "+" if delta > 0 else ""
        print(f"{name:<30} {b_val:>12} {f_val:>12} {sign}{delta:>11}")

    # Per-domain comparison
    print(f"\n{'Domain':<15} {'Baseline avg ms':>18} {'FGL avg ms':>18} {'Overhead ms':>18}")
    print(f"{'-'*69}")
    all_domains = set(list(b_summary.get("by_domain", {}).keys()) + list(f_summary.get("by_domain", {}).keys()))
    for domain in sorted(all_domains):
        b_d = b_summary.get("by_domain", {}).get(domain, {})
        f_d = f_summary.get("by_domain", {}).get(domain, {})
        b_lat = b_d.get("avg_latency_ms", 0)
        f_lat = f_d.get("avg_latency_ms", 0)
        overhead = f_lat - b_lat
        print(f"{domain:<15} {b_lat:>18.1f} {f_lat:>18.1f} {overhead:>+18.1f}")

    # Claim-level metrics
    b_claims = compute_claim_metrics(baseline["results"])
    f_claims = compute_claim_metrics(fgl["results"])

    print(f"\n{'Claim Metric':<30} {'Baseline':>12} {'+ FGL':>12}")
    print(f"{'-'*54}")
    print(f"{'Response rate (%)':30} {b_claims['response_rate']:>12} {f_claims['response_rate']:>12}")
    print(f"{'Expected claims':30} {b_claims['total_expected_claims']:>12} {f_claims['total_expected_claims']:>12}")

    # Save comparison
    comparison = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "baseline_file": baseline_path.name,
        "fgl_file": fgl_path.name,
        "baseline_metadata": b_meta,
        "fgl_metadata": f_meta,
        "summary_comparison": {
            name: {"baseline": b_val, "fgl": f_val, "delta": f_val - b_val}
            for name, b_val, f_val in metrics
        },
        "claim_metrics": {
            "baseline": b_claims,
            "fgl": f_claims,
        },
    }

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"comparison_{date_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)

    print(f"\n  Comparison saved to: {out_path}")
    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description="Compare baseline vs FGL results")
    parser.add_argument("--baseline", type=str, default="", help="Path to baseline results JSON")
    parser.add_argument("--fgl", type=str, default="", help="Path to FGL results JSON")
    parser.add_argument("--auto", action="store_true", help="Auto-find latest results")

    args = parser.parse_args()

    if args.auto or (not args.baseline and not args.fgl):
        baseline_path = find_latest_result("baseline_")
        fgl_path = find_latest_result("with_fgl_")
        if not baseline_path:
            print("No baseline results found. Run benchmark.runner first.")
            sys.exit(1)
        if not fgl_path:
            print("No FGL results found. Run benchmark.evaluate first.")
            sys.exit(1)
    else:
        baseline_path = Path(args.baseline)
        fgl_path = Path(args.fgl)

    if not baseline_path.exists():
        print(f"Baseline file not found: {baseline_path}")
        sys.exit(1)
    if not fgl_path.exists():
        print(f"FGL file not found: {fgl_path}")
        sys.exit(1)

    compare(baseline_path, fgl_path)


if __name__ == "__main__":
    main()
