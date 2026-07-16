from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "salidas"


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(100.0 * numerator / denominator, 2)


def _series_count_pct(series: pd.Series) -> list[dict]:
    counts = series.fillna("NA").value_counts(dropna=False)
    total = int(counts.sum())
    rows = []
    for key, value in counts.items():
        count = int(value)
        rows.append(
            {
                "value": str(key),
                "count": count,
                "pct": _pct(count, total),
            }
        )
    return rows


def _pairs(df: pd.DataFrame) -> set[tuple[int, int]]:
    if df.empty:
        return set()
    pairs_df = df[["project_id", "publication_id"]].dropna().drop_duplicates().astype(int)
    return set(tuple(x) for x in pairs_df.to_numpy())


def main() -> None:
    summary_path = OUT / "00_summary.json"
    gt_results = pd.read_csv(OUT / "06_project_results_ground_truth.csv")
    gt_publications = pd.read_csv(OUT / "07_project_publication_ground_truth.csv")
    candidates = pd.read_csv(OUT / "05_project_publication_candidates_v1.csv")

    candidates["confidence_norm"] = (
        candidates["confidence"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace({"alta": "high", "media": "medium", "baja": "low"})
    )

    linked_results = gt_results[gt_results["publication_id"].notna()].copy()

    gt_total_rows = int(len(gt_results))
    gt_total_projects = int(gt_results["project_id"].nunique())

    linked_rows = int(len(linked_results))
    linked_projects = int(linked_results["project_id"].nunique())

    gt_pairs = _pairs(gt_publications)
    all_candidate_pairs = _pairs(candidates)

    matched_all = len(all_candidate_pairs & gt_pairs)

    confidence_metrics = {}
    for confidence in ["high", "medium"]:
        conf_pairs = _pairs(candidates[candidates["confidence_norm"] == confidence])
        matched = len(conf_pairs & gt_pairs)
        confidence_metrics[confidence] = {
            "candidate_pairs": len(conf_pairs),
            "matched_pairs": matched,
            "precision_pct": _pct(matched, len(conf_pairs)),
            "recall_pct": _pct(matched, len(gt_pairs)),
        }

    high_medium_pairs = _pairs(candidates[candidates["confidence_norm"].isin(["high", "medium"])])
    matched_high_medium = len(high_medium_pairs & gt_pairs)

    project_hit = linked_results.groupby("project_id").size()
    linked_per_project = {
        "mean": round(float(project_hit.mean()), 2) if len(project_hit) else 0.0,
        "median": round(float(project_hit.median()), 2) if len(project_hit) else 0.0,
        "max": int(project_hit.max()) if len(project_hit) else 0,
    }

    result = {
        "ground_truth_overview": {
            "rows_total": gt_total_rows,
            "projects_total": gt_total_projects,
            "rows_linked_publication": linked_rows,
            "rows_linked_publication_pct": _pct(linked_rows, gt_total_rows),
            "projects_with_linked_publication": linked_projects,
            "projects_with_linked_publication_pct": _pct(linked_projects, gt_total_projects),
            "unique_project_publication_pairs": len(gt_pairs),
            "linked_publications_per_project": linked_per_project,
        },
        "distribution": {
            "result_type": _series_count_pct(linked_results["result_type"]),
            "result_category": _series_count_pct(linked_results["result_category"]),
            "match_method": _series_count_pct(linked_results["match_method"]),
            "call_name": _series_count_pct(linked_results["call_name"]),
        },
        "efficacy": {
            "overall": {
                "candidate_pairs": len(all_candidate_pairs),
                "matched_pairs": matched_all,
                "precision_pct": _pct(matched_all, len(all_candidate_pairs)),
                "recall_pct": _pct(matched_all, len(gt_pairs)),
            },
            "by_confidence": confidence_metrics,
            "high_plus_medium": {
                "candidate_pairs": len(high_medium_pairs),
                "matched_pairs": matched_high_medium,
                "precision_pct": _pct(matched_high_medium, len(high_medium_pairs)),
                "recall_pct": _pct(matched_high_medium, len(gt_pairs)),
            },
        },
    }

    # Keep top sections concise for slide usage.
    top_types = sorted(result["distribution"]["result_type"], key=lambda x: x["count"], reverse=True)[:10]

    md_lines = [
        "# Ground Truth Metrics (Omar)",
        "",
        "## Overview",
        f"- Total rows in ground truth: {gt_total_rows}",
        f"- Total projects in ground truth: {gt_total_projects}",
        f"- Rows linked to publication_id: {linked_rows} ({_pct(linked_rows, gt_total_rows)}%)",
        f"- Projects with >=1 linked publication: {linked_projects} ({_pct(linked_projects, gt_total_projects)}%)",
        f"- Unique project-publication pairs in GT: {len(gt_pairs)}",
        f"- Linked publications per project (mean / median / max): {linked_per_project['mean']} / {linked_per_project['median']} / {linked_per_project['max']}",
        "",
        "## Product Type Mix (Top 10 among linked rows)",
    ]

    for row in top_types:
        md_lines.append(f"- {row['value']}: {row['count']} ({row['pct']}%)")

    md_lines.extend(
        [
            "",
            "## Efficacy vs Ground Truth",
            f"- Overall precision (matched candidates / all candidates): {result['efficacy']['overall']['precision_pct']}%",
            f"- Overall recall (matched GT pairs / all GT pairs): {result['efficacy']['overall']['recall_pct']}%",
            f"- High confidence precision / recall: {result['efficacy']['by_confidence']['high']['precision_pct']}% / {result['efficacy']['by_confidence']['high']['recall_pct']}%",
            f"- Medium confidence precision / recall: {result['efficacy']['by_confidence']['medium']['precision_pct']}% / {result['efficacy']['by_confidence']['medium']['recall_pct']}%",
            f"- High+Medium precision / recall: {result['efficacy']['high_plus_medium']['precision_pct']}% / {result['efficacy']['high_plus_medium']['recall_pct']}%",
            "",
            "## Quick Talking Points",
            "- Most linked products are indexed articles, followed by indexed conference proceedings.",
            "- Linked rows are split between Adicional and Comprometido categories.",
            "- All linked rows in GT were matched by DOI in the current data slice.",
            "- High confidence provides materially better precision than Medium.",
        ]
    )

    (OUT / "00_ground_truth_metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "00_ground_truth_metrics_slide.md").write_text("\n".join(md_lines), encoding="utf-8")

    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}

    summary.update(
        {
            "ground_truth_linked_rows": linked_rows,
            "ground_truth_linked_rows_pct": _pct(linked_rows, gt_total_rows),
            "ground_truth_linked_projects": linked_projects,
            "ground_truth_linked_projects_pct": _pct(linked_projects, gt_total_projects),
            "ground_truth_linked_top_result_type": top_types[0]["value"] if top_types else None,
            "efficacy_high_precision_pct": result["efficacy"]["by_confidence"]["high"]["precision_pct"],
            "efficacy_high_recall_pct": result["efficacy"]["by_confidence"]["high"]["recall_pct"],
            "efficacy_medium_precision_pct": result["efficacy"]["by_confidence"]["medium"]["precision_pct"],
            "efficacy_medium_recall_pct": result["efficacy"]["by_confidence"]["medium"]["recall_pct"],
        }
    )

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result["ground_truth_overview"], ensure_ascii=False, indent=2))
    print(json.dumps(result["efficacy"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
