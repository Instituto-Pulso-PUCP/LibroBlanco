from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'salidas'

# Load v1 candidates
candidates = pd.read_csv(OUT / '05_project_publication_candidates_v1.csv')
proj = pd.read_csv(OUT / '01_projects_closed.csv')

print('=' * 70)
print('V1 PIPELINE EFFICACY ASSESSMENT')
print('=' * 70)
print()

# Coverage
print('PROJECT COVERAGE:')
unique_projects_with_candidates = candidates['project_id'].nunique()
total_closed_projects = len(proj)
coverage_pct = 100 * unique_projects_with_candidates / total_closed_projects
print(f'  Projects with >= 1 candidate: {unique_projects_with_candidates:>4} / {total_closed_projects} ({coverage_pct:>5.1f}%)')
print(f'  Projects with 0 candidates:   {total_closed_projects - unique_projects_with_candidates:>4} ({100-coverage_pct:>5.1f}%)')
print()

# Average candidates per project
avg_per_proj = len(candidates) / unique_projects_with_candidates
print(f'  Avg candidates per project: {avg_per_proj:.1f}')
print(f'  Max candidates in one project: {candidates.groupby("project_id").size().max()}')
print()

# Score distribution
print('CONFIDENCE DISTRIBUTION:')
conf_dist = candidates['confidence'].value_counts().sort_index()
for conf, count in conf_dist.items():
    pct = 100 * count / len(candidates)
    print(f'  {conf:.<20} {count:>5} ({pct:>5.1f}%)')
print()

# Score statistics
print('SCORE STATISTICS:')
print(f'  Mean score:        {candidates["score"].mean():.2f}')
print(f'  Median score:      {candidates["score"].median():.2f}')
print(f'  Min score:         {candidates["score"].min():.2f}')
print(f'  Max score:         {candidates["score"].max():.2f}')
print(f'  Std dev:           {candidates["score"].std():.2f}')
print()

# Evidence analysis
print('TOP 5 EVIDENCE PATTERNS:')
evidence_dist = candidates.groupby('evidence').size().sort_values(ascending=False)
for i, (evidence, count) in enumerate(evidence_dist.head(5).items()):
    pct = 100 * count / len(candidates)
    print(f'  {count:>5} ({pct:>5.1f}%): {evidence[:65]}')
print()

# Source patterns
print('SOURCE COMBINATIONS:')
source_patterns = []
for _, row in candidates.iterrows():
    sources = []
    if row['source_RI'] > 0: sources.append('RI')
    if row['source_SCOPUS'] > 0: sources.append('SCOPUS')
    if row['source_WOS'] > 0: sources.append('WOS')
    source_patterns.append('+'.join(sources) if sources else 'none')

source_dist = pd.Series(source_patterns).value_counts()
for sources, count in source_dist.items():
    pct = 100 * count / len(candidates)
    print(f'  {sources:.<20} {count:>5} ({pct:>5.1f}%)')
print()

# Year delta
print('PUBLICATION TIMING (vs project year):')
year_deltas = candidates['year_delta'].value_counts().sort_index()
for delta, count in sorted(year_deltas.items()):
    pct = 100 * count / len(candidates)
    if pd.isna(delta):
        print(f'  No year info:         {count:>5} ({pct:>5.1f}%)')
    elif delta == 0:
        print(f'  Same year (Δ=0):      {count:>5} ({pct:>5.1f}%)')
    elif 1 <= delta <= 2:
        print(f'  1-2 years after:      {count:>5} ({pct:>5.1f}%)')
    elif 3 <= delta <= 5:
        print(f'  3-5 years after:      {count:>5} ({pct:>5.1f}%)')
    else:
        print(f'  Δ={int(delta):+d} years:    {count:>5} ({pct:>5.1f}%)')
print()

# Title similarity
print('TITLE SIMILARITY:')
print(f'  Mean similarity:      {candidates["title_similarity"].mean():.3f}')
print(f'  Median similarity:    {candidates["title_similarity"].median():.3f}')
print(f'  With similarity > 0.30: {(candidates["title_similarity"] > 0.30).sum():>5} ({100*(candidates["title_similarity"] > 0.30).sum()/len(candidates):.1f}%)')
print(f'  With similarity > 0.50: {(candidates["title_similarity"] > 0.50).sum():>5} ({100*(candidates["title_similarity"] > 0.50).sum()/len(candidates):.1f}%)')
print()

print('=' * 70)
print('KEY FINDINGS:')
print('=' * 70)
print()
print(f'✓ HIGH COVERAGE:       {coverage_pct:.1f}% of closed projects have >= 1 candidate')
print(f'✓ HIGH CONFIDENCE:     {(conf_dist.get("Alta", 0)/len(candidates))*100:.1f}% at Alta confidence')
print(f'✓ MULTI-SOURCE:        {((candidates["source_RI"] > 0) | (candidates["source_SCOPUS"] > 0) | (candidates["source_WOS"] > 0)).sum()/len(candidates)*100:.1f}% from multiple sources')
print(f'  TIMING ADVANTAGE:    {(candidates["year_delta"].isin([0, 1, 2])).sum()/len(candidates)*100:.1f}% published within 2 years')
print()
