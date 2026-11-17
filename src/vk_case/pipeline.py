"""Content-addressed runs, artifact verification, atomic publication."""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import openpyxl
import pandas as pd
import yaml
from pypdf import PdfReader

from .audit import run_audit
from .charts import build_figures
from .economics import reference_reproduction, scenario_tables
from .evidence import claims
from .experiments import available_power, detectable_difference, plan_sample
from .ingest import DataError, digest, load, locate
from .metrics import calculate, content_comparisons, metric_catalog, robustness
from .reporting import ROOT, build_reports
from .slides import build_source, export_slides

REQUIRED = ["metrics.json", "tables/pilot_candidates.csv", "tables/business_features.parquet",
            "audit/issues.csv", "audit/independent_checks.csv", "reports/report.md", "reports/report.pdf",
            "reports/appendix.pdf", "reports/report_metrics.json", "slides/strategy_draft.pdf",
            "slides/strategy_draft.pptx", "slides/slides_source.json", "figures/scenarios.png"]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str))


def load_config(path=None):
    config = yaml.safe_load(Path(path or ROOT/"config/project.yaml").read_text())
    required = {"scenarios", "economics", "experiment", "team", "seed", "bootstrap_repetitions", "minimum_group"}
    if not isinstance(config, dict) or not required.issubset(config):
        raise DataError(f"В конфигурации нужны разделы: {', '.join(sorted(required))}")
    if not config["scenarios"] or config["bootstrap_repetitions"] < 20 or config["minimum_group"] < 1:
        raise DataError("Нужны сценарии, не менее 20 bootstrap-повторов и положительный размер группы.")
    names = [s.get("name") for s in config["scenarios"]]
    if len(names) != len(set(names)):
        raise DataError("Названия сценариев должны быть уникальны.")
    if set(names) != {"Низкий", "Базовый", "Высокий", "Стресс"}:
        raise DataError("Для согласованных материалов нужны четыре сценария: Низкий, Базовый, Высокий, Стресс.")
    config["scenarios"] = sorted(config["scenarios"], key=lambda s: ["Низкий", "Базовый", "Высокий", "Стресс"].index(s["name"]))
    members = config["team"].get("members")
    if not isinstance(members, list) or len(members) != 4:
        raise DataError("team.members должен содержать четыре имени или четыре null.")
    universities = config["team"].get("universities")
    if universities is not None and (not isinstance(universities, list) or len(universities) != 4):
        raise DataError("team.universities должен содержать четыре названия вузов.")
    return config


def implementation_hash():
    paths = sorted((ROOT/"src/vk_case").glob("*.py"))
    paths += [ROOT/f"docs/{n}.md" for n in ["strategy", "methodology", "experiment_plan", "limitations", "team_workplan"]]
    paths += [ROOT/"research/sources.yaml", ROOT/"research/competitor_matrix.csv", ROOT/"config/baseline_reference.yaml", ROOT/"uv.lock"]
    paths += sorted((ROOT/"assets/fonts").glob("*.ttf"))
    h = sha256()
    for path in paths:
        h.update(str(path.relative_to(ROOT)).encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def independent_checks(workbook, metrics):
    """Read with openpyxl + Python scalar operations, independently of pandas transforms."""
    w = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    sheet = w["Бизнесы"]
    rows = list(sheet.values)
    headers = {h: i for i, h in enumerate(rows[0])}
    rows = rows[1:]
    def get(row, name):
        return row[headers[name]]
    goods = [r for r in rows if get(r, "Тип бизнеса (товары / услуги)") in {"товарное", "товарное и услужное"}]
    cand = [r for r in goods if get(r, "Число активных товаров в каталоге") > 0
            and get(r, "Просмотры товарного контента") > 0 and get(r, "Заказы через чекаут") == 0]
    total_orders = sum(get(r, "Заказы через чекаут") for r in goods)
    total_gmv = sum(get(r, "GMV через чекаут, ₽") for r in goods)
    checks = {
        "businesses": len(rows), "goods_businesses": len(goods),
        "selling_goods": sum(get(r, "Заказы через чекаут") > 0 for r in goods),
        "goods_orders": total_orders, "goods_gmv": total_gmv,
        "goods_aov": total_gmv/total_orders if total_orders else None,
        "all_orders": sum(get(r, "Заказы через чекаут") for r in rows),
        "all_sellers": sum(get(r, "Заказы через чекаут") > 0 for r in rows),
        "original_missing": sum(get(r, "Автор оригинального контента (оценка модели)") is None for r in rows),
        "missing_aov_sellers": sum(get(r, "Заказы через чекаут") > 0 and get(r, "Средний чек, ₽") is None for r in rows),
        "orders_without_current_checkout": sum(get(r, "Заказы через чекаут") > 0 and get(r, "Подключён чекаут") == 0 for r in rows),
        "candidates": len(cand),
        "candidates_handmade": sum(get(r, "Тематика") == "Творчество и хендмейд" for r in cand),
        "candidates_hobby": sum(get(r, "Тематика") == "Развлечения и хобби" for r in cand),
        "candidates_food": sum(get(r, "Тематика") == "Кулинария и еда" for r in cand),
    }
    w.close()
    return pd.DataFrame([{"metric_id": k, "independent": v, "pipeline": metrics[k],
                          "matches": v == metrics[k]} for k, v in checks.items()])


def verify(run_dir, check_input=True):
    run_dir = Path(run_dir)
    manifest_file = run_dir/"manifest.json"
    if not manifest_file.is_file():
        raise DataError("Манифест запуска не найден.")
    manifest = json.loads(manifest_file.read_text())
    if manifest["status"] not in {"completed", "completed_with_warnings"}:
        raise DataError(f"Запуск не завершён: {manifest['status']}")
    for name in REQUIRED:
        if not (run_dir/name).is_file():
            raise DataError(f"Отсутствует обязательный результат: {name}")
    for name, expected in manifest["artifacts"].items():
        path = run_dir/name
        if not path.is_file() or digest(path) != expected:
            raise DataError(f"Нарушена целостность результата: {name}")
    if check_input:
        relative = manifest.get("workbook_project_path")
        path = ROOT/relative if relative and (ROOT/relative).is_file() else Path(manifest["workbook_path"])
        if not path.is_file() or digest(path) != manifest["workbook_sha256"]:
            raise DataError("Исходный XLSX отсутствует или изменился после расчёта.")
    metrics = json.loads((run_dir/"metrics.json").read_text())
    deck = json.loads((run_dir/"slides/slides_source.json").read_text())
    if deck["run_id"] != manifest["run_id"] or deck["metrics"] != metrics:
        raise DataError("Слайды не согласованы с метриками выбранного запуска.")
    if json.loads((run_dir/"reports/report_metrics.json").read_text()) != metrics:
        raise DataError("Отчёт не согласован с метриками выбранного запуска.")
    if len(PdfReader(run_dir/"slides/strategy_draft.pdf").pages) != 8:
        raise DataError("Основная презентация должна содержать ровно 8 страниц.")
    independent = pd.read_csv(run_dir/"audit/independent_checks.csv")
    if len(independent) < 10 or not independent.matches.all():
        raise DataError("Не прошла независимая сверка чисел.")
    return {"run_id": manifest["run_id"], "status": manifest["status"],
            "artifacts_verified": len(manifest["artifacts"]), "independent_checks": len(independent),
            "slides": 8, "submission_ready": manifest["submission_ready"]}


def latest(output_dir):
    output_dir = Path(output_dir)
    path = output_dir/"current_run.json"
    if not path.is_file():
        raise DataError("Завершённого запуска нет. Сначала выполните vk-case run.")
    pointer = json.loads(path.read_text())
    return output_dir/pointer["run_dir"]


def run(input_dir=Path("data/raw"), output_dir=Path("outputs"), workbook=None, config_path=None):
    workbook = locate(Path(input_dir), Path(workbook) if workbook else None)
    config = load_config(config_path)
    input_hash, code_hash = digest(workbook), implementation_hash()
    config_hash = sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    run_id = sha256(f"{input_hash}:{code_hash}:{config_hash}".encode()).hexdigest()[:16]
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/"runs").mkdir(exist_ok=True)
    final = output_dir/"runs"/run_id
    if final.exists():
        verify(final)
        publish_pointer(output_dir, run_id)
        return final
    staging = Path(tempfile.mkdtemp(prefix=f".building-{run_id}-", dir=output_dir))
    manifest = {"run_id": run_id, "status": "incomplete", "workbook_path": str(workbook.relative_to(ROOT)) if workbook.is_relative_to(ROOT) else str(workbook),
                "workbook_project_path": str(workbook.relative_to(ROOT)) if workbook.is_relative_to(ROOT) else None,
                "workbook_sha256": input_hash, "implementation_sha256": code_hash,
                "config_sha256": config_hash, "started_at": datetime.now(timezone.utc).isoformat(),
                "submission_ready": False, "artifacts": {}}
    write_json(staging/"manifest.json", manifest)
    try:
        for d in ["tables", "audit", "figures", "reports", "slides"]:
            (staging/d).mkdir()
        bundle = load(workbook)
        metrics, tables = calculate(bundle)
        tables["content_comparisons"], tables["content_strata"] = content_comparisons(
            tables["business_features"], config["seed"], config["bootstrap_repetitions"])
        tables["comparable_groups"]["interpretable_size"] = tables["comparable_groups"].n >= config["minimum_group"]
        comparison_rows = []
        for keys, group in tables["comparable_groups"].groupby(["theme", "audience_band", "ad_active"], dropna=False):
            if set(group.checkout) != {0, 1}:
                continue
            no, yes = group[group.checkout == 0].iloc[0], group[group.checkout == 1].iloc[0]
            comparison_rows.append({"theme": keys[0], "audience_band": keys[1], "ad_active": keys[2],
                                    "n_checkout_0": int(no.n), "n_checkout_1": int(yes.n),
                                    "seller_share_0": no.seller_share, "seller_share_1": yes.seller_share,
                                    "difference_pp": (yes.seller_share-no.seller_share)*100,
                                    "interpretable_size": min(no.n, yes.n) >= config["minimum_group"],
                                    "interpretation": "описательная связь текущего чекаута и продаж, не причинный эффект"})
        tables["checkout_associations"] = pd.DataFrame(comparison_rows)
        tables["robustness"] = robustness(tables["business_features"])
        for key in ["totals", "daily", "sources", "categories", "demography", "regions", "cell_status"]:
            tables[key] = getattr(bundle, key)
        tables["weekly_events"] = bundle.daily[bundle.daily.aggregation == "sum"].groupby(
            [pd.Grouper(key="date", freq="7D", origin=bundle.daily.date.min()), "metric_id", "scope"],
            dropna=False).value.sum(min_count=1).reset_index()
        audit = run_audit(bundle, tables["business_features"])
        audit.to_csv(staging/"audit/issues.csv", index=False)
        tables["business_features"].isna().sum().rename("missing_count").to_csv(staging/"audit/missingness.csv")
        ref = yaml.safe_load((ROOT/"config/baseline_reference.yaml").read_text())
        pd.DataFrame([{"metric_id": k, "current": metrics.get(k), "reference": v,
                       "matches": metrics.get(k) == v, "source_sha256": input_hash,
                       "note": "независимый ориентир старого плана; не используется в расчёте"}
                      for k, v in ref.items()]).to_csv(staging/"audit/baseline_comparison.csv", index=False)
        independent = independent_checks(workbook, metrics)
        independent.to_csv(staging/"audit/independent_checks.csv", index=False)
        if not independent.matches.all():
            raise DataError("Независимый пересчёт не совпал с ядром.")
        scenarios, sensitivity, periods = scenario_tables(metrics, config)
        tables.update(scenarios=scenarios, sensitivity=sensitivity, scenario_periods=periods,
                      reference_reproduction=pd.DataFrame(reference_reproduction()))
        experiment = plan_sample(**config["experiment"])
        experiment["available_power"] = available_power(max(4, metrics["candidates"]), **{
            k: config["experiment"][k] for k in ["p0", "p1", "alpha", "ratio"]}) if metrics["candidates"] >= 4 else None
        experiment["available_n"] = metrics["candidates"]
        experiment["detectable_difference"] = detectable_difference(metrics["candidates"],
            config["experiment"]["p0"]) if metrics["candidates"] >= 4 else None
        write_json(staging/"experiment.json", experiment)
        sources = pd.DataFrame(yaml.safe_load((ROOT/"research/sources.yaml").read_text()))
        tables["competitor_matrix"] = pd.read_csv(ROOT/"research/competitor_matrix.csv")
        claim_table = claims(metrics, scenarios, tables["content_comparisons"])
        tables["research_sources"], tables["claims"] = sources, claim_table
        provenance = [{"table": name, "period": bundle.period, "source_sha256": input_hash,
                       "transformation_sha256": code_hash, "run_id": run_id} for name in tables]
        tables["provenance"] = pd.DataFrame(provenance)
        for name, table in tables.items():
            table.to_csv(staging/f"tables/{name}.csv", index=False)
            if name in {"business_features", "pilot_candidates"}:
                table.to_parquet(staging/f"tables/{name}.parquet", index=False)
        write_json(staging/"metrics.json", metrics)
        write_json(staging/"metric_catalog.json", metric_catalog(metrics, bundle))
        write_json(staging/"schema.json", bundle.schema)
        write_json(staging/"configuration.json", config)
        fig_meta = build_figures(staging/"figures", bundle, tables, metrics, scenarios, sensitivity)
        write_json(staging/"figures/catalog.json", fig_meta)
        build_reports(staging, run_id, metrics, tables, audit, scenarios, experiment, config, sources, claim_table)
        for name in ["strategy", "methodology", "experiment_plan", "limitations", "team_workplan"]:
            shutil.copy2(ROOT/f"docs/{name}.md", staging/f"reports/{name}.md")
        export_slides(staging, build_source(metrics, config, scenarios, experiment, run_id))
        if digest(workbook) != input_hash:
            raise DataError("Исходный файл изменился во время запуска.")
        team = config["team"]
        ready = bool(team.get("name") and team.get("city") and all(team["members"]))
        manifest.update(status="completed_with_warnings" if len(audit) or not ready else "completed",
                        period=bundle.period, submission_ready=ready,
                        readiness_limitations=[] if ready else ["Название команды, город и состав не заполнены; презентация — черновик"],
                        warnings=len(audit), sheets_read=len(bundle.schema),
                        completed_at=datetime.now(timezone.utc).isoformat())
        manifest["artifacts"] = {str(p.relative_to(staging)): digest(p) for p in sorted(staging.rglob("*"))
                                 if p.is_file() and p.name != "manifest.json"}
        write_json(staging/"manifest.json", manifest)
        verify(staging)
        staging.rename(final)
        publish_pointer(output_dir, run_id)
        return final
    except Exception as exc:
        manifest.update(status="failed", failure=f"{type(exc).__name__}: {exc}")
        write_json(staging/"manifest.json", manifest)
        failure_dir = output_dir/"failed"
        failure_dir.mkdir(exist_ok=True)
        shutil.move(str(staging), str(failure_dir/staging.name.lstrip(".")))
        raise


def publish_pointer(output_dir, run_id):
    pointer = output_dir/".current_run.json.tmp"
    write_json(pointer, {"run_id": run_id, "run_dir": f"runs/{run_id}"})
    os.replace(pointer, output_dir/"current_run.json")
