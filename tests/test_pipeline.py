import json
import shutil
from pathlib import Path

import pytest
import yaml
from pypdf import PdfReader

from vk_case.ingest import DataError
from vk_case.pipeline import latest, run, verify


def test_full_fixture_run_determinism_and_artifacts(small_workbook, fast_config, tmp_path, monkeypatch):
    a = run(workbook=small_workbook, output_dir=tmp_path/"a", config_path=fast_config)
    b = run(workbook=small_workbook, output_dir=tmp_path/"b", config_path=fast_config)
    assert json.loads((a/"metrics.json").read_text()) == json.loads((b/"metrics.json").read_text())
    assert a.name == b.name
    assert latest(tmp_path/"a") == a
    checked = verify(a)
    assert checked["slides"] == 8
    assert checked["status"] == "completed_with_warnings"
    assert checked["independent_checks"] == 15
    assert checked["submission_ready"] is True
    deck = json.loads((a/"slides/slides_source.json").read_text())
    expected_team = yaml.safe_load(fast_config.read_text())["team"]
    assert deck["draft"] is False
    assert deck["team"] == expected_team
    pdf = PdfReader(a/"slides/strategy_draft.pdf")
    team_page = pdf.pages[1].extract_text()
    for member in expected_team["members"]:
        assert member in team_page
    for university in set(expected_team["universities"]):
        assert university in team_page
    assert "имя не указано" not in team_page
    assert "черновик" not in pdf.metadata.title.lower()
    from vk_case import pipeline
    manifest = json.loads((a/"manifest.json").read_text())
    manifest["workbook_path"] = "/missing/original.xlsx"
    manifest["workbook_project_path"] = "relocated.xlsx"
    shutil.copy2(small_workbook, tmp_path/"relocated.xlsx")
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    (a/"manifest.json").write_text(json.dumps(manifest))
    assert verify(a)["slides"] == 8
    (a/"tables/pilot_candidates.csv").write_text("tampered")
    with pytest.raises(DataError, match="целостность"):
        verify(a)


def test_no_input_no_false_success(tmp_path):
    with pytest.raises(DataError):
        run(input_dir=tmp_path, output_dir=tmp_path/"out")
    assert not (tmp_path/"out/current_run.json").exists()


def test_config_changes_tables_figures_and_preserves_current_on_failure(small_workbook, fast_config, tmp_path):
    output = tmp_path/"configured"
    a = run(workbook=small_workbook, output_dir=output, config_path=fast_config)
    config = yaml.safe_load(fast_config.read_text())
    config["scenarios"][1]["delta_activation"] = .08
    fast_config.write_text(yaml.safe_dump(config, allow_unicode=True))
    b = run(workbook=small_workbook, output_dir=output, config_path=fast_config)
    assert a.name != b.name
    assert (a/"tables/scenarios.csv").read_bytes() != (b/"tables/scenarios.csv").read_bytes()
    assert (a/"figures/scenarios.png").read_bytes() != (b/"figures/scenarios.png").read_bytes()
    config["scenarios"][1]["realized_value_share"] = 1.5
    fast_config.write_text(yaml.safe_dump(config, allow_unicode=True))
    with pytest.raises(ValueError):
        run(workbook=small_workbook, output_dir=output, config_path=fast_config)
    assert latest(output) == b


def test_real_workbook_if_present(tmp_path, fast_config):
    path = Path("data/raw/dataset.xlsx")
    if not path.exists():
        pytest.skip("Реальный вход отсутствует; фикстурный прогон остаётся автономным.")
    result = run(workbook=path, output_dir=tmp_path/"real", config_path=fast_config)
    assert verify(result)["artifacts_verified"] >= 40
