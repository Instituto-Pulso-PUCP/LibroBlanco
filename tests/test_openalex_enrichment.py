import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(ROOT))

import openalex_helpers as oh


def test_build_openalex_query_uses_title_when_doi_missing():
    query = oh.build_openalex_query(doi=None, title="A study about open science")
    assert "search.exact" in query
    assert "A%20study%20about%20open%20science" in query


def test_extract_openalex_enrichment_parses_oa_fields():
    payload = {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1000/test",
        "display_name": "Test paper",
        "publication_year": 2022,
        "cited_by_count": 11,
        "primary_location": {
            "is_oa": True,
            "landing_page_url": "https://example.org/article",
            "source": {"display_name": "Nature"},
            "license": "cc-by",
        },
        "authorships": [{"author": {"display_name": "Jane Doe"}}],
    }

    result = oh.extract_openalex_enrichment(payload, doi="10.1000/test", title="Test paper")

    assert result["openalex_work_id"] == "https://openalex.org/W123"
    assert result["openalex_is_oa"] is True
    assert result["openalex_oa_status"] == "green"
    assert result["openalex_oa_url"] == "https://example.org/article"
    assert result["openalex_publication_year"] == 2022
    assert result["openalex_cited_by_count"] == 11
    assert result["openalex_authors"] == "Jane Doe"
    assert result["openalex_institution_names"] == ""
    assert result["openalex_institution_country_codes"] == ""
