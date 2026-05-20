import json
from pathlib import Path
from malibbene.sources_v2.attractions.llm_extract import (
    write_extraction_request, load_extraction_result,
)

def test_write_extraction_request_creates_pending_file(tmp_path):
    write_extraction_request(
        target_kind="visitor_eligibility",
        slug="mfa",
        html_path=tmp_path/"mfa.html",
        out_dir=tmp_path/"_pending",
        prompt_template="Extract visitor_eligibility from this museum's About page: {html}",
    )
    pending = tmp_path/"_pending"/"visitor_eligibility"/"mfa.json"
    assert pending.exists()
    data = json.loads(pending.read_text())
    assert data["status"] == "pending"
    assert "html_path" in data and "prompt_template" in data

def test_load_extraction_result_reads_subagent_output(tmp_path):
    d = tmp_path/"visitor_eligibility"
    d.mkdir(parents=True)
    (d/"mfa.json").write_text(json.dumps({
        "status":"ok","extracted":{"residency":"none","source_phrase":"open to all"},
    }))
    result = load_extraction_result(target_kind="visitor_eligibility", slug="mfa", base_dir=tmp_path)
    assert result["extracted"]["residency"] == "none"
