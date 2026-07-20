"""Helper script for visualizing project semantic vectorization results.

This is intentionally not a pytest file. It lives under tests/ for convenience,
but it is a helper script that can be run directly to inspect analysis output.
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

DEFAULT_OUTPUT = Path("salidas/project_semantic_analysis.csv")


def load_analysis_csv(path: Path = DEFAULT_OUTPUT) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Expected analysis CSV at {path}. Run scripts/project_semantic_analysis.py first."
        )
    df = pd.read_csv(path, dtype=str)
    numeric_cols = [col for col in df.columns if col.startswith("pca_") or col == "cluster_label"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def summarize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    summary = pd.DataFrame(
        {
            "total_projects": [len(df)],
            "cluster_count": [df["cluster_label"].nunique() if "cluster_label" in df.columns else 0],
            "empty_texts": [df["project_text"].isna().sum() if "project_text" in df.columns else 0],
        }
    )
    return summary


def plot_pca_scatter(df: pd.DataFrame, output_dir: Path = Path("tests/visualizations")) -> Path:
    if "pca_1" not in df.columns or "pca_2" not in df.columns:
        raise ValueError("CSV must contain pca_1 and pca_2 columns.")
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 8))
    cluster_labels = df["cluster_label"] if "cluster_label" in df.columns else None
    scatter = ax.scatter(
        df["pca_1"],
        df["pca_2"],
        c=cluster_labels.astype(float) if cluster_labels is not None else None,
        cmap="tab10",
        alpha=0.75,
        edgecolors="w",
        linewidths=0.5,
        s=50,
    )
    ax.set_title("PCA Scatter of Project Vectorization")
    ax.set_xlabel("PCA 1")
    ax.set_ylabel("PCA 2")
    if cluster_labels is not None:
        legend1 = ax.legend(*scatter.legend_elements(), title="Cluster")
        ax.add_artist(legend1)
    output_path = output_dir / "pca_scatter.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_cluster_counts(df: pd.DataFrame, output_dir: Path = Path("tests/visualizations")) -> Path:
    if "cluster_label" not in df.columns:
        raise ValueError("CSV must contain cluster_label column.")
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = df["cluster_label"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(8, 5))
    counts.plot(kind="bar", ax=ax, color="tab:blue", edgecolor="black")
    ax.set_title("Project Counts by Cluster")
    ax.set_xlabel("Cluster Label")
    ax.set_ylabel("Project Count")
    output_path = output_dir / "cluster_counts.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def print_examples_by_cluster(df: pd.DataFrame, n_examples: int = 2) -> None:
    if "cluster_label" not in df.columns:
        print("No cluster_label column found. Cannot print cluster examples.")
        return
    if "Título" not in df.columns and "title" not in df.columns:
        print("No title column found. Showing first rows of project_text instead.")
    print("\nExamples by cluster:")
    for cluster, group in df.groupby("cluster_label"):
        print(f"\nCluster {cluster} ({len(group)} projects):")
        for idx, row in group.head(n_examples).iterrows():
            title = row.get("Título") or row.get("title") or "<no title>"
            sample_text = row.get("project_text", "<no project_text>")
            print(f"  - {title}")
            print(f"    text snippet: {sample_text[:140].replace('\n', ' ')}")


def plot_text_length_hist(df: pd.DataFrame, output_dir: Path = Path("tests/visualizations")) -> Path:
    if "project_text" not in df.columns:
        raise ValueError("CSV must contain project_text column.")
    output_dir.mkdir(parents=True, exist_ok=True)
    lengths = df["project_text"].fillna("").map(len)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(lengths, bins=30, color="tab:purple", edgecolor="black", alpha=0.8)
    ax.set_title("Distribution of Project Text Length")
    ax.set_xlabel("Text Length (characters)")
    ax.set_ylabel("Number of Projects")
    output_path = output_dir / "text_length_hist.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def main() -> None:
    output = DEFAULT_OUTPUT
    print(f"Loading analysis results from {output}")
    df = load_analysis_csv(output)
    print(summarize_dataframe(df).to_string(index=False))
    print_examples_by_cluster(df, n_examples=2)
    print("\nGenerating visualizations...")
    pca_path = plot_pca_scatter(df)
    counts_path = plot_cluster_counts(df)
    hist_path = plot_text_length_hist(df)
    print(f"Saved PCA scatter to {pca_path}")
    print(f"Saved cluster counts to {counts_path}")
    print(f"Saved text-length histogram to {hist_path}")


if __name__ == "__main__":
    main()
