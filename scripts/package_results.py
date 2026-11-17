"""Copy the selected verified run into a reviewable local handoff folder."""

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from vk_case.pipeline import latest, verify

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--archive", action="store_true")
parser.add_argument("--output-dir", type=Path, default=root/"outputs")
args, _ = parser.parse_known_args()
run = latest(args.output_dir)
checked = verify(run)
config = json.loads((run/"configuration.json").read_text())
team = config["team"]
deck_name = "WW_team_strategy_spb" + ("" if checked["submission_ready"] else "_DRAFT")
target = root/"deliverables"
target.mkdir(exist_ok=True)
copies = {
    "slides/strategy_draft.pdf": f"{deck_name}.pdf",
    "slides/strategy_draft.pptx": f"{deck_name}.pptx",
    "reports/report.pdf": "research.pdf", "reports/report.md": "research.md",
    "reports/appendix.pdf": "appendix.pdf", "reports/appendix.md": "appendix.md",
    "tables/pilot_candidates.csv": "pilot_candidates.csv", "tables/scenarios.csv": "scenarios.csv",
    "tables/claims.csv": "claims.csv", "audit/issues.csv": "data_audit.csv",
}
for source, name in copies.items():
    shutil.copy2(run/source, target/name)
shutil.copy2(run/"tables/claims.csv", root/"research/claims.csv")
(target/"verification.json").write_text(json.dumps(checked, ensure_ascii=False, indent=2))
(target/"START_HERE.md").write_text(f"""# WW team · Санкт-Петербург

Начните с восьмислайдового {deck_name}.pdf. Состав команды и вузы включены в PDF, PPTX и исследование. Для воспроизводимого обновления измените config/project.yaml и выполните ./scripts/recalculate.

research.pdf — исследование, экономика и эксперимент. appendix.pdf — доказательства, аудит, задачи и FAQ. pilot_candidates.csv — кандидаты для ручной квалификации, не гарантированные новые продавцы.

Расчёт: {checked['run_id']}. Все 7 листов; 15 независимых сверок. Команда: {', '.join(name or 'имя не указано' for name in team['members'])}. Интервью, действующие тарифы/затраты и причинный эффект требуют проверки командой. Демо не является результатом эксперимента.

Приложение: ./scripts/start-app → http://127.0.0.1:8501. Подробные команды — в README.md. Репозиторий: https://github.com/Arsenyyya/WW-team-VK. Сдача через форму чемпионата не выполнялась.
""")
if args.archive:
    archive = target/"WW_team_casechamp_project.zip"
    files = []
    for folder in ["src", "app", "scripts", "config", "research", "docs", "assets", ".streamlit", "tests", "data/raw"]:
        files.extend(p for p in (root/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.extend(root/name for name in ["README.md", "pyproject.toml", "uv.lock", ".gitignore", "input_manifest.json"])
    files.append(root/"outputs/current_run.json")
    files.extend(p for p in run.rglob("*") if p.is_file())
    files.extend(target/name for name in [*copies.values(), "START_HERE.md", "verification.json"])
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for file in files:
            z.write(file, str(file.relative_to(root)))
    print(f"Архив: {archive} ({archive.stat().st_size/1e6:.1f} МБ)")
print(f"Материалы: {target}; run {checked['run_id']}")
