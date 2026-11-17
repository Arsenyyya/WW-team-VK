
import numpy as np
import openpyxl
import pytest

from vk_case.audit import run_audit
from vk_case.ingest import DataError, availability, digest, load, validate_headers
from vk_case.metrics import calculate, features, ratio


def test_named_columns_and_original_unchanged(small_workbook, tmp_path):
    before = digest(small_workbook)
    original = load(small_workbook)
    w = openpyxl.load_workbook(small_workbook)
    sheet = w["Бизнесы"]
    rows = list(sheet.values)
    w.remove(sheet)
    sheet = w.create_sheet("Бизнесы")
    for row in rows:
        sheet.append(list(row)[::-1])
    shuffled = tmp_path/"reordered.xlsx"
    w.save(shuffled)
    a, _ = calculate(original)
    b, _ = calculate(load(shuffled))
    assert a == b
    assert digest(small_workbook) == before


def test_collision_is_not_first_match():
    with pytest.raises(DataError, match="Неоднозначные"):
        validate_headers(["ID бизнеса", "ID\u00a0бизнеса"], {"ID бизнеса": "id"})


def test_availability_and_int64(small_workbook):
    assert [availability(v) for v in [0, None, "—"]] == ["available", "missing", "dash_unavailable"]
    b = load(small_workbook)
    assert b.business.original_content.isna().sum() == 1
    assert b.business.original_content.eq(0).sum() == 7
    assert np.int64(4_777_750_023) > 2**32
    assert ratio(0, 0) is None


def test_weighted_aov_candidates_and_source_axes(small_workbook):
    bundle = load(small_workbook)
    m, tables = calculate(bundle)
    assert m["goods_businesses"] == 6
    assert m["goods_orders"] == 4
    assert m["goods_aov"] == 750
    assert len(tables["pilot_candidates"]) == 4
    assert tables["pilot_candidates"].orders.eq(0).all()
    main = bundle.sources[~bundle.sources.is_nested].groupby("scope").opens.sum()
    assert main["partner"] == bundle.total("opens", "partner")
    assert bundle.daily.query("metric_id == 'unique_viewers'").aggregation.eq("non_additive").all()
    assert not any(run_audit(bundle, tables["business_features"]).check_id.str.startswith("daily_sum_unique"))


def test_zero_gmv_aov_and_types(small_workbook):
    b = load(small_workbook).business
    b.loc[0, "gmv"] = 0
    b.loc[0, "reported_aov"] = 10
    enriched = features(b)
    assert enriched.loc[0, "aov"] == 0
    assert not enriched.loc[6, "is_goods"]
    issues = run_audit(load(small_workbook), enriched)
    assert "reported_aov_over_5pct" in issues.check_id.values


def test_inconsistency_preserved(small_workbook):
    bundle = load(small_workbook)
    bundle.categories.loc[(bundle.categories.scope == "market") & (bundle.categories.metric_id == "orders"), "value"] += 5
    m, tables = calculate(bundle)
    issues = run_audit(bundle, tables["business_features"])
    assert m["market_category_orders"] == m["market_orders"] + 10
    assert "categories_orders" in issues.check_id.values
    assert bundle.total("orders") == 300


def test_duplicate_id_and_empty_are_errors(small_workbook):
    w = openpyxl.load_workbook(small_workbook)
    w["Бизнесы"].cell(3, 1, 1)
    w.save(small_workbook)
    with pytest.raises(DataError, match="ID"):
        load(small_workbook)
    w["Бизнесы"].delete_rows(2, 100)
    w.save(small_workbook)
    with pytest.raises(DataError, match="пуст"):
        load(small_workbook)
