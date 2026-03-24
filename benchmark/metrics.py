"""
Metrics calculator for Factual Grounding Layer evaluation.

Computes metrics from evaluate.py results (with grounding data) and
optionally compares them against baseline results.

Metrics computed:
  - Claim-Level Precision (CLP): supported_claims / total_claims
  - Unsupported Claim Rate (UCR): claims_with_no_evidence / total_claims
  - Refuted Claim Rate (RCR): refuted_claims / total_claims
  - Hallucination Rate: responses with at least 1 unverified/refuted claim
  - Source Citation Rate: responses that cite at least 1 source
  - Evidence Recall: expected claims covered by verified claims
  - Grounding Pipeline Latency: avg / p50 / p95
  - Per-domain breakdown of all metrics

Usage:
    python -m benchmark.metrics --results results/with_fgl_gpt-4o_*.json
    python -m benchmark.metrics --results results/with_fgl_*.json --baseline results/baseline_*.json
    python -m benchmark.metrics --auto
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

RESULTS_DIR = Path(__file__).parent / "results"


# ─── Loaders ───────────────────────────────────────────────────────────────

def find_latest_result(prefix: str) -> Optional[Path]:
    """Find the most recent result file with given prefix."""
    files = sorted(RESULTS_DIR.glob(f"{prefix}*.json"), reverse=True)
    return files[0] if files else None


def load_result(filepath: Path) -> Dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Per-question grounding metrics ───────────────────────────────────────

def compute_question_metrics(item: Dict[str, Any]) -> Dict[str, Any]:
    """Compute grounding metrics for a single question result."""
    gr = item.get("grounding")
    if not gr:
        return {
            "has_grounding": False,
            "claims_total": 0,
            "claims_verified": 0,
            "claims_refuted": 0,
            "claims_unverified": 0,
            "claims_skipped": 0,
            "clp": None,
            "ucr": None,
            "rcr": None,
            "has_hallucination": None,
            "has_source_citation": False,
            "evidence_recall": None,
            "pipeline_duration_ms": 0,
        }

    total = gr["claims_total"]
    verified = gr["claims_verified"]
    refuted = gr["claims_refuted"]
    unverified = gr["claims_unverified"]
    skipped = gr["claims_skipped"]

    # Claims that were actually checked (excluding skipped)
    checked = total - skipped

    # Claim-Level Precision: verified / checked
    clp = verified / checked if checked > 0 else None

    # Unsupported Claim Rate: unverified / checked
    ucr = unverified / checked if checked > 0 else None

    # Refuted Claim Rate: refuted / checked
    rcr = refuted / checked if checked > 0 else None

    # Hallucination: at least 1 unverified or refuted claim
    has_hallucination = (refuted + unverified) > 0 if checked > 0 else None

    # Source citation: at least 1 source cited
    has_source_citation = len(gr.get("sources_cited", [])) > 0

    # Evidence Recall: how many expected claims are covered by verified verdicts
    evidence_recall = _compute_evidence_recall(item, gr)

    return {
        "has_grounding": True,
        "claims_total": total,
        "claims_verified": verified,
        "claims_refuted": refuted,
        "claims_unverified": unverified,
        "claims_skipped": skipped,
        "clp": clp,
        "ucr": ucr,
        "rcr": rcr,
        "has_hallucination": has_hallucination,
        "has_source_citation": has_source_citation,
        "evidence_recall": evidence_recall,
        "pipeline_duration_ms": gr.get("pipeline_duration_ms", 0),
    }


def _compute_evidence_recall(item: Dict, gr: Dict) -> Optional[float]:
    """
    Evidence Recall: what fraction of expected claims are covered
    by at least one verified verdict?

    Uses simple substring matching between expected claim text and
    verified verdict claim_text.
    """
    expected = item.get("expected_claims", [])
    if not expected:
        return None

    verdicts = gr.get("verdicts", [])
    verified_texts = [
        v["claim_text"].lower()
        for v in verdicts
        if v.get("status") == "verified"
    ]

    if not verified_texts:
        return 0.0

    covered = 0
    for exp in expected:
        exp_text = exp["text"].lower()
        # Check if any verified claim covers this expected claim
        # Use token overlap: if >50% of expected claim tokens appear in a verified claim
        exp_tokens = set(exp_text.split())
        for vt in verified_texts:
            vt_tokens = set(vt.split())
            if not exp_tokens:
                break
            overlap = len(exp_tokens & vt_tokens) / len(exp_tokens)
            if overlap > 0.5:
                covered += 1
                break

    return covered / len(expected)


# ─── Aggregate metrics ────────────────────────────────────────────────────

def aggregate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate metrics across all questions."""
    per_question = [compute_question_metrics(r) for r in results]
    grounded = [q for q in per_question if q["has_grounding"]]

    if not grounded:
        return {"error": "No results with grounding data found"}

    n = len(grounded)

    # Collect non-None values
    clps = [q["clp"] for q in grounded if q["clp"] is not None]
    ucrs = [q["ucr"] for q in grounded if q["ucr"] is not None]
    rcrs = [q["rcr"] for q in grounded if q["rcr"] is not None]
    halls = [q["has_hallucination"] for q in grounded if q["has_hallucination"] is not None]
    recalls = [q["evidence_recall"] for q in grounded if q["evidence_recall"] is not None]
    durations = [q["pipeline_duration_ms"] for q in grounded if q["pipeline_duration_ms"] > 0]

    # Total claim counts
    total_claims = sum(q["claims_total"] for q in grounded)
    total_verified = sum(q["claims_verified"] for q in grounded)
    total_refuted = sum(q["claims_refuted"] for q in grounded)
    total_unverified = sum(q["claims_unverified"] for q in grounded)
    total_skipped = sum(q["claims_skipped"] for q in grounded)
    total_checked = total_claims - total_skipped

    return {
        "questions_total": len(results),
        "questions_with_grounding": n,

        # Aggregate Claim-Level Precision (micro-averaged)
        "claim_level_precision_micro": (
            total_verified / total_checked if total_checked > 0 else None
        ),
        # Macro-averaged (per-question average)
        "claim_level_precision_macro": (
            sum(clps) / len(clps) if clps else None
        ),

        # Unsupported Claim Rate (micro)
        "unsupported_claim_rate_micro": (
            total_unverified / total_checked if total_checked > 0 else None
        ),
        "unsupported_claim_rate_macro": (
            sum(ucrs) / len(ucrs) if ucrs else None
        ),

        # Refuted Claim Rate (micro)
        "refuted_claim_rate_micro": (
            total_refuted / total_checked if total_checked > 0 else None
        ),

        # Hallucination Rate: % of responses with at least 1 bad claim
        "hallucination_rate": (
            sum(1 for h in halls if h) / len(halls) if halls else None
        ),

        # Source Citation Rate: % of responses with sources
        "source_citation_rate": (
            sum(1 for q in grounded if q["has_source_citation"]) / n
        ),

        # Evidence Recall (macro)
        "evidence_recall_macro": (
            sum(recalls) / len(recalls) if recalls else None
        ),

        # Claim counts
        "claims_total": total_claims,
        "claims_verified": total_verified,
        "claims_refuted": total_refuted,
        "claims_unverified": total_unverified,
        "claims_skipped": total_skipped,

        # Latency
        "grounding_latency_avg_ms": (
            round(sum(durations) / len(durations), 1) if durations else None
        ),
        "grounding_latency_p50_ms": (
            round(sorted(durations)[len(durations) // 2], 1) if durations else None
        ),
        "grounding_latency_p95_ms": (
            round(sorted(durations)[int(len(durations) * 0.95)], 1) if durations else None
        ),
    }


def aggregate_by_domain(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Compute aggregate metrics per domain."""
    domains: Dict[str, List[Dict]] = {}
    for r in results:
        d = r.get("domain", "unknown")
        domains.setdefault(d, []).append(r)

    return {domain: aggregate_metrics(items) for domain, items in sorted(domains.items())}


# ─── Baseline comparison ──────────────────────────────────────────────────

def compute_baseline_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute basic metrics from baseline (no grounding) results."""
    successful = [r for r in results if r.get("status") == "ok"]
    latencies = [r["latency_ms"] for r in successful]

    total_expected_claims = sum(
        len(r.get("expected_claims", [])) for r in results
    )

    return {
        "questions_total": len(results),
        "questions_successful": len(successful),
        "response_rate": round(len(successful) / len(results) * 100, 1) if results else 0,
        "total_expected_claims": total_expected_claims,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "p50_latency_ms": round(sorted(latencies)[len(latencies) // 2], 1) if latencies else 0,
        "p95_latency_ms": (
            round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if latencies else 0
        ),
    }


# ─── Display ──────────────────────────────────────────────────────────────

def _fmt(val, pct=False) -> str:
    """Format a metric value for display."""
    if val is None:
        return "N/A"
    if pct:
        return f"{val * 100:.1f}%"
    if isinstance(val, float):
        return f"{val:.3f}"
    return str(val)


def print_metrics(fgl_path: Path, baseline_path: Optional[Path] = None):
    """Print all computed metrics."""
    fgl_data = load_result(fgl_path)
    fgl_results = fgl_data["results"]
    fgl_meta = fgl_data["metadata"]

    agg = aggregate_metrics(fgl_results)
    by_domain = aggregate_by_domain(fgl_results)

    print(f"\n{'=' * 70}")
    print(f"FACTUAL GROUNDING LAYER — METRICS REPORT")
    print(f"{'=' * 70}")
    print(f"  File:            {fgl_path.name}")
    print(f"  Model:           {fgl_meta.get('model', 'N/A')}")
    print(f"  Grounding model: {fgl_meta.get('grounding_model', 'N/A')}")
    print(f"  Grounding mode:  {fgl_meta.get('grounding_mode', 'N/A')}")
    print(f"  Questions:       {agg['questions_total']} total, {agg['questions_with_grounding']} with grounding")

    # ── Core Factual Grounding Metrics ──
    print(f"\n{'─' * 70}")
    print(f"  FACTUAL GROUNDING METRICS")
    print(f"{'─' * 70}")
    print(f"  {'Claim-Level Precision (micro):':<40} {_fmt(agg['claim_level_precision_micro'], pct=True)}")
    print(f"  {'Claim-Level Precision (macro):':<40} {_fmt(agg['claim_level_precision_macro'], pct=True)}")
    print(f"  {'Unsupported Claim Rate (micro):':<40} {_fmt(agg['unsupported_claim_rate_micro'], pct=True)}")
    print(f"  {'Refuted Claim Rate (micro):':<40} {_fmt(agg['refuted_claim_rate_micro'], pct=True)}")
    print(f"  {'Hallucination Rate:':<40} {_fmt(agg['hallucination_rate'], pct=True)}")
    print(f"  {'Source Citation Rate:':<40} {_fmt(agg['source_citation_rate'], pct=True)}")
    print(f"  {'Evidence Recall (macro):':<40} {_fmt(agg['evidence_recall_macro'], pct=True)}")

    # ── Claim Counts ──
    print(f"\n{'─' * 70}")
    print(f"  CLAIM COUNTS")
    print(f"{'─' * 70}")
    print(f"  {'Total claims:':<40} {agg['claims_total']}")
    print(f"  {'Verified:':<40} {agg['claims_verified']}")
    print(f"  {'Refuted:':<40} {agg['claims_refuted']}")
    print(f"  {'Unverified:':<40} {agg['claims_unverified']}")
    print(f"  {'Skipped:':<40} {agg['claims_skipped']}")

    # ── Latency ──
    print(f"\n{'─' * 70}")
    print(f"  GROUNDING LATENCY")
    print(f"{'─' * 70}")
    print(f"  {'Avg:':<40} {_fmt(agg['grounding_latency_avg_ms'])} ms")
    print(f"  {'P50:':<40} {_fmt(agg['grounding_latency_p50_ms'])} ms")
    print(f"  {'P95:':<40} {_fmt(agg['grounding_latency_p95_ms'])} ms")

    # ── Per-domain ──
    print(f"\n{'─' * 70}")
    print(f"  PER-DOMAIN BREAKDOWN")
    print(f"{'─' * 70}")
    header = f"  {'Domain':<12} {'CLP':>8} {'UCR':>8} {'Hall%':>8} {'Recall':>8} {'N':>5}"
    print(header)
    print(f"  {'─' * 55}")
    for domain, dm in by_domain.items():
        print(
            f"  {domain:<12} "
            f"{_fmt(dm.get('claim_level_precision_micro'), pct=True):>8} "
            f"{_fmt(dm.get('unsupported_claim_rate_micro'), pct=True):>8} "
            f"{_fmt(dm.get('hallucination_rate'), pct=True):>8} "
            f"{_fmt(dm.get('evidence_recall_macro'), pct=True):>8} "
            f"{dm.get('questions_with_grounding', 0):>5}"
        )

    # ── Baseline comparison ──
    if baseline_path:
        baseline_data = load_result(baseline_path)
        baseline_results = baseline_data["results"]
        b_meta = baseline_data["metadata"]
        b_metrics = compute_baseline_metrics(baseline_results)

        fgl_latencies = [r["latency_ms"] for r in fgl_results if r.get("status") == "ok"]
        fgl_avg_lat = round(sum(fgl_latencies) / len(fgl_latencies), 1) if fgl_latencies else 0

        print(f"\n{'─' * 70}")
        print(f"  BASELINE COMPARISON")
        print(f"{'─' * 70}")
        print(f"  Baseline file:   {baseline_path.name}")
        print(f"  Baseline model:  {b_meta.get('model', 'N/A')}")
        print()
        print(f"  {'Metric':<35} {'Baseline':>12} {'+ FGL':>12} {'Delta':>12}")
        print(f"  {'─' * 71}")
        print(f"  {'Avg latency (ms)':<35} {b_metrics['avg_latency_ms']:>12} {fgl_avg_lat:>12} {fgl_avg_lat - b_metrics['avg_latency_ms']:>+12.1f}")
        print(f"  {'Source Citation Rate':<35} {'N/A':>12} {_fmt(agg['source_citation_rate'], pct=True):>12} {'':>12}")
        print(f"  {'Claim-Level Precision':<35} {'N/A':>12} {_fmt(agg['claim_level_precision_micro'], pct=True):>12} {'':>12}")
        print(f"  {'Hallucination Rate':<35} {'N/A':>12} {_fmt(agg['hallucination_rate'], pct=True):>12} {'':>12}")
        print(f"  {'Latency overhead (ms)':<35} {'—':>12} {'':>12} {fgl_avg_lat - b_metrics['avg_latency_ms']:>+12.1f}")

    # ── Per-question detail ──
    print(f"\n{'─' * 70}")
    print(f"  PER-QUESTION DETAIL")
    print(f"{'─' * 70}")
    header = f"  {'ID':<10} {'Domain':<10} {'Claims':>6} {'V':>3} {'R':>3} {'U':>3} {'CLP':>7} {'Recall':>7} {'Lat ms':>8}"
    print(header)
    print(f"  {'─' * 65}")
    for r in fgl_results:
        qm = compute_question_metrics(r)
        if not qm["has_grounding"]:
            continue
        print(
            f"  {r['id']:<10} "
            f"{r['domain']:<10} "
            f"{qm['claims_total']:>6} "
            f"{qm['claims_verified']:>3} "
            f"{qm['claims_refuted']:>3} "
            f"{qm['claims_unverified']:>3} "
            f"{_fmt(qm['clp'], pct=True):>7} "
            f"{_fmt(qm['evidence_recall'], pct=True):>7} "
            f"{qm['pipeline_duration_ms']:>8.0f}"
        )

    print(f"\n{'=' * 70}\n")

    # ── Save metrics JSON ──
    from datetime import datetime
    output = {
        "metadata": fgl_meta,
        "aggregate": agg,
        "by_domain": by_domain,
        "per_question": [
            {"id": r["id"], "domain": r["domain"], **compute_question_metrics(r)}
            for r in fgl_results
        ],
    }
    if baseline_path:
        output["baseline"] = compute_baseline_metrics(load_result(baseline_path)["results"])

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_safe = fgl_meta.get("model", "unknown").replace("/", "_")
    out_path = RESULTS_DIR / f"metrics_{model_safe}_{date_str}.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Metrics saved to: {out_path}\n")


# ─── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compute FGL metrics from evaluation results")
    parser.add_argument("--results", type=str, default="", help="Path to FGL results JSON")
    parser.add_argument("--baseline", type=str, default="", help="Path to baseline results JSON (optional)")
    parser.add_argument("--auto", action="store_true", help="Auto-find latest results")

    args = parser.parse_args()

    if args.auto or not args.results:
        fgl_path = find_latest_result("with_fgl_")
        if not fgl_path:
            print("No FGL results found. Run benchmark.evaluate first.")
            sys.exit(1)
        baseline_path = find_latest_result("baseline_")
    else:
        fgl_path = Path(args.results)
        baseline_path = Path(args.baseline) if args.baseline else None

    if not fgl_path.exists():
        print(f"FGL results not found: {fgl_path}")
        sys.exit(1)
    if baseline_path and not baseline_path.exists():
        print(f"Baseline not found: {baseline_path}, skipping comparison")
        baseline_path = None

    print_metrics(fgl_path, baseline_path)


if __name__ == "__main__":
    main()
