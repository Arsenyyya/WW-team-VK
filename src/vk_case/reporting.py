"""Editable research report and vector PDF, from the selected completed run."""

import json
import re
from html import escape
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
INK, BLUE, MUTED = "#15263E", "#1768F2", "#6B7A90"


def register_fonts():
    for name, filename in [("Case", "DejaVuSans.ttf"), ("CaseBold", "DejaVuSans-Bold.ttf")]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(ROOT/"assets/fonts"/filename)))
    pdfmetrics.registerFontFamily("Case", normal="Case", bold="CaseBold", italic="Case", boldItalic="CaseBold")


def number(value, decimals=0):
    if value is None or pd.isna(value):
        return "недоступно"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def md_table(rows, columns):
    header = "| " + " | ".join(columns) + " |"
    lines = [header, "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in row) + " |")
    return "\n".join(lines)


def markup(text):
    text = escape(str(text))
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<font color='#1768F2'>\1</font>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"<a href='\2' color='#1768F2'>\1</a>", text)
    return text


def pdf_from_markdown(text, target, run_id, figures=None, title="Исследование", author="WW team", draft=False):
    register_fonts()
    body = ParagraphStyle("CaseBody", fontName="Case", fontSize=9.6, leading=14.6, textColor=INK,
                          spaceAfter=7, alignment=TA_LEFT)
    h1 = ParagraphStyle("CaseH1", parent=body, fontName="CaseBold", fontSize=23, leading=29, spaceAfter=18, keepWithNext=True)
    h2 = ParagraphStyle("CaseH2", parent=body, fontName="CaseBold", fontSize=15, leading=21,
                        spaceBefore=15, spaceAfter=10, keepWithNext=True)
    h2_table = ParagraphStyle("CaseTableH2", parent=h2, keepWithNext=False)
    h3 = ParagraphStyle("CaseH3", parent=h2, fontSize=11, leading=16)
    cell = ParagraphStyle("CaseCell", parent=body, fontSize=8.2, leading=12, spaceAfter=0)
    story = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [x.strip() for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", c) for c in cells):
                    rows.append(cells)
                i += 1
            if len(rows[0]) > 4:
                for row in rows[1:]:
                    story.append(Paragraph(markup(row[0]), h3))
                    for key, value in zip(rows[0][1:], row[1:], strict=True):
                        story.append(Paragraph(f"<b>{markup(key)}.</b> {markup(value)}", body))
                continue
            ncols = len(rows[0])
            weights = [.30, .18, .18, .34] if ncols == 4 else [.30, .32, .38] if ncols == 3 else [1/ncols]*ncols
            table = Table([[Paragraph(markup(c), cell) for c in row] for row in rows],
                          colWidths=[174*mm*w for w in weights], repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9F0FA")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, -1), .35, colors.HexColor("#DFE6EF")),
            ]))
            story.extend([table, Spacer(1, 10)])
            continue
        if line.startswith("### "):
            story.append(Paragraph(markup(line[4:]), h3))
        elif line.startswith("## "):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            next_is_table = j < len(lines) and lines[j].strip().startswith("|")
            story.append(Paragraph(markup(line[3:]), h2_table if next_is_table else h2))
        elif line.startswith("# "):
            story.append(Paragraph(markup(line[2:]), h1))
        elif line.startswith("![") and figures:
            ref = re.search(r"\((.+?)\)", line)
            if ref:
                path = Path(figures)/ref.group(1)
                img = Image(str(path))
                scale = min(174*mm/img.imageWidth, 125*mm/img.imageHeight)
                img.drawWidth, img.drawHeight = img.imageWidth*scale, img.imageHeight*scale
                story.append(KeepTogether([img, Spacer(1, 12)]))
        else:
            if line.startswith("- "):
                line = "• " + line[2:]
            story.append(Paragraph(markup(line), body))
        i += 1
    doc = SimpleDocTemplate(str(target), pagesize=(210*mm, 297*mm), rightMargin=18*mm, leftMargin=18*mm,
                            topMargin=22*mm, bottomMargin=22*mm, title=title, author=author)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.setFont("Case", 7)
        label = "ИССЛЕДОВАТЕЛЬСКИЙ ЧЕРНОВИК" if draft else "WW TEAM  /  ИССЛЕДОВАНИЕ"
        canvas.drawString(18*mm, 285*mm, f"VK CASE CHAMP 2026  /  {label}")
        canvas.line(18*mm, 17*mm, 192*mm, 17*mm)
        canvas.drawString(18*mm, 12*mm, f"Сентябрь 2026 · run {run_id}")
        canvas.drawRightString(192*mm, 12*mm, str(document.page))
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def build_reports(run_dir, run_id, metrics, tables, audit, scenarios, experiment, config, sources, claims):
    d = Path(run_dir)/"reports"
    d.mkdir(exist_ok=True)
    m = metrics
    team = config['team']
    team_ready = bool(team.get('name') and team.get('city') and all(team.get('members', [])))
    members = team.get('members') or [None]*4
    universities = team.get('universities') or ['не указан']*4
    team_table = md_table([(name or 'не указано', university) for name, university in zip(members, universities, strict=True)], ['Участник', 'Вуз'])
    team_status = 'Состав команды заполнен по предоставленным данным.' if team_ready else 'Презентация остаётся черновиком до заполнения состава команды.'
    paired = tables['content_comparisons'].iloc[0]
    paired_note = "включает ноль" if paired.ci_low <= 0 <= paired.ci_high else "не включает ноль"
    baseline = scenarios[scenarios.name == "Базовый"].iloc[0]
    payback_note = (f"достигается на {int(baseline.payback_month)}-м месяце" if pd.notna(baseline.payback_month)
                    else "не достигается на заданном горизонте")
    scenario_specs = "; ".join(f"{s['name']}: {number(s['delta_activation']*100,2)} п.п., {number(s['orders_per_seller'],2)} заказа, {number(s['realized_value_share']*100,1)}% стоимости" for s in scenarios.to_dict('records'))
    fact_rows = [
        ("Товарная / смешанная база", number(m["goods_businesses"]), "type ∈ товарное, товарное и услужное"),
        ("С внутренними заказами", f"{number(m['selling_goods'])} / {number(m['goods_businesses'])} = {number(m['seller_share']*100, 2)}%", "Уникальные business_id; orders>0"),
        ("Заказы / GMV товарной базы", f"{number(m['goods_orders'])} / {number(m['goods_gmv'])} ₽", "Суммы соответствующих полей"),
        ("Взвешенный чек", f"{number(m['goods_aov'], 6)} ₽", "ΣGMV / Σзаказов"),
        ("Кандидаты", number(m["candidates"]), "Товарный тип, каталог>0, товарные просмотры>0, заказы=0"),
        ("Хендмейд / хобби / еда / мода", " / ".join(number(m[f"candidates_{k}"]) for k in ["handmade", "hobby", "food", "fashion"]), "Число кандидатов по тематике, не товарной категории"),
        ("Главная в открытиях Маркета", f"{number(m['homepage_share']*100, 3)}%", f"{number(m['homepage_opens'])} / {number(m['market_opens'])}"),
        ("GMV десяти крупнейших", f"{number(m['gmv_top_10_share']*100, 2)}%", "GMV top10 / GMV товарной базы"),
        ("Неизвестная оригинальность", f"{number(m['original_missing'])} / {number(m['businesses'])}", "Пропуск не равен неоригинальности"),
        ("Средний DAU / MAU", f"{number(m['dau_mau_ratio']*100, 2)}%", "Общий контур; не аудитория всех товарных показов"),
    ]
    summary = f"""# От интереса к заказу

Исследование социальной коммерции для VK Case Champ 2026. Период: {tables['provenance'].iloc[0]['period']}. Версия материалов: {config.get('prepared_on', '2026-11-17')}. Внешние источники проверены 17 ноября 2026. Run: `{run_id}`. XLSX SHA-256: `{tables['provenance'].iloc[0]['source_sha256']}`.

**Рекомендация.** Проверить небольшой пакет ясных условий и оформления для готовых товарных продавцов. Маркет — общий товарный слой; отдельная главная получает инвестиции после доказательства дополнительного эффекта. Первый сегмент — мастерские и небольшие бренды; локальная еда — второй маршрут после технического пилота.

**Статус.** Аналитический результат рассчитан на данных кейса. Команда: {team.get('name') or 'не указана'}; город: {team.get('city') or 'не указан'}. {team_status} Интервью и эксперимент не проведены. Факты, интерпретации и сценарии разделены в реестре утверждений.

{team_table}

## Проверенные факты и их база

{md_table(fact_rows, ['Показатель', 'Результат', 'Знаменатель / определение'])}

![Готовность и заказы](readiness.png)

## Что данные меняют в решении

Доля продающих {number(m['seller_share']*100, 2)}% показывает разрыв между товарным присутствием и наблюдаемыми заказами, но не объясняет причину. {number(m['candidates'])} кандидатов позволяют проверить путь у уже имеющих каталог и просмотры. До приглашения необходимо подтвердить ассортимент, наличие, желание продавца и его владельца.

Темы хендмейда и хобби дают {number(m['candidates_handmade']+m['candidates_hobby'])} кандидатов, еда — {number(m['candidates_food'])}. Это обоснование доступного списка для исследования, а не доказанная оценка размера сегмента или спроса.

Главная даёт {number(m['homepage_share']*100, 3)}% открытий товаров Маркета. Рационально начать с компонентов, работающих в других входах, и отдельно проверить главную. Вывод о её закрытии не следует из доли: нет заказов, затрат и вклада по поверхности.

В сопоставимой парной подбазе наблюдается {int(paired['n'])} бизнесов. Интервал логарифма отношения просмотров на публикацию в текущем расчёте {paired_note}: {number(paired.ci_low,6)} … {number(paired.ci_high,6)}. Это описательное сравнение доступной подбазы, не общий причинный эффект контента. Тезис об универсальном ухудшении распространения товарного контента не используем как установленный факт. См. таблицу content_comparisons и оговорку о трактовке публикаций в методике.

На десять крупнейших товарных бизнесов приходится {number(m['gmv_top_10_share']*100, 2)}% GMV. Чек и суммарный GMV чувствительны к составу базы; таблица robustness показывает результаты без крупнейших и без спорных строк.

## Ограничения, которые нельзя спрятать

Зарегистрировано {len(audit)} наблюдений аудита (особенности и расхождения, не число испорченных строк). Заказы категорий Маркета: {number(m['market_category_orders'])}; итог: {number(m['market_orders'])}. Причина неизвестна, цифры сохранены. У партнёра есть прямой путь мимо карточки. Его заказы/открытия нельзя считать чистой конверсией карточки. Низкое число зарегистрированных оплат не доказывает потери остальных заказов.

![Источники](traffic_sources.png)

## Описательные отношения двух товарных контуров

{md_table([(s, number(m[f'{s}_open_impression_ratio']*100,3)+'%', number(m[f'{s}_order_open_ratio']*100,3)+'%', number(m[f'{s}_aov'],2)+' ₽') for s in ['market','partner']], ['Контур', 'Открытия / показы', 'Заказы / открытия', 'ΣGMV / Σзаказов'])}

Первые два столбца — отношения событий с разным охватом; это не причинная воронка и не доказательство превосходства одного пути. Дневные уникальные не суммируются в месячных. Источники не складываются с вложенной реферальной строкой.

"""
    scenario_rows = [(r['name'], number(r['delta_sellers'],2), number(r['delta_orders'],2), number(r['gmv_realized'])+' ₽') for r in scenarios.to_dict('records')]
    economics = f"""
## Сценарная экономика

{md_table(scenario_rows, ['Допущение', 'Доп. продавцы', 'Доп. заказы', 'Сохранённая стоимость'])}

Формула: Δпродавцы = N × Δактивация; Δзаказы = Δпродавцы × частота; созданный GMV = Δзаказы × AOV; сохранённая стоимость = созданный GMV × доля после невыполнения/возвратов. N={number(m['candidates'])}; AOV={number(m['goods_aov'],6)} ₽. Ожидания не округляются до конца расчёта.

Допущения сценариев: {scenario_specs}. Это не вероятности и не результаты пилота. Исторический ноль кандидатов не означает будущий p0=0.

Прибыль продавца = сохранённая стоимость × валовая маржа − дополнительные привлечение, исполнение и возвратная логистика, сервисы и труд. В конфигурации маржа неизвестна, поэтому прибыль недоступна. Валовая маржа должна исключать уже учтённую себестоимость; повторно её не вычитаем.

Вклад VK = дополнительная рекламная выручка + чистый сервисный и партнёрский доход − переменные расходы, субсидии, поддержка и потерянный существующий вклад. Условная чистая ставка {number(config['economics']['net_service_rate']*100,2)}% не является тарифом VK. Нулевые дополнительные расходы и рекламный/партнёрский доход — упрощения, требующие замены фактическими вводными. Возможные модели монетизации не ограничены комиссией.

Инвестиции модели: {number(config['economics']['investment'])} ₽. Независимый иллюстративный пример сметы на 574 000 ₽: исследование 32 ч × 1 500 ₽ = 48 000 ₽; дизайн 48 × 2 000 = 96 000 ₽; разработка 120 × 2 500 = 300 000 ₽; QA 40 × 1 500 = 60 000 ₽; аналитика 28 × 2 500 = 70 000 ₽. Это редактируемый пример часов и ставок, не рыночная оценка и не утверждение доступного бюджета.

Модель горизонта: одна первоначальная когорта, удержание {number(config['economics']['retention']*100)}% в месяц, горизонт {config['economics']['horizon_months']} месяцев, без новых когорт. В базовом иллюстративном расчёте окупаемость {payback_note}. Сохранённая стоимость учитывает возвраты один раз. Модель чувствительности меняет N, активацию, частоту, чек, выполнение и чистую ставку.

![Сценарии](scenarios.png)

![Чувствительность](sensitivity.png)

## Размер эксперимента

Иллюстративный расчёт: p0={number(experiment['p0']*100,2)}%, p1={number(experiment['p1']*100,2)}%, двусторонний alpha={number(experiment['alpha']*100)}%, мощность {number(experiment['power']*100)}%. Нужно {number(experiment['n_control'])} в контроле и {number(experiment['n_treatment'])} в тесте, всего {number(experiment['n_total'])}. Метод: {experiment['method']}. Единица — независимый бизнес; общие владельцы требуют кластеризации.

На {number(m['candidates'])} кандидатах иллюстративная мощность для этих p0/p1 — {number(experiment['available_power']*100 if experiment['available_power'] is not None else None,1)}%. Это демонстрирует ограничение набора, а не знание реального p0 кандидатов. Качественный пилот и причинный тест — разные этапы.

"""
    report = summary + (ROOT/"docs/strategy.md").read_text().split("\n",1)[1] + economics
    report += "\n\n## Матрица каналов и статус проверки\n\n" + md_table(
        [(r.channel, r.seller_job + ". " + r.costs, r.verification + ". " + r.limitations + " ["+r.source_ids+"]")
         for r in tables["competitor_matrix"].itertuples()], ["Канал", "Задача и состав затрат", "Ограничение доказательств"])
    for name in ["methodology", "experiment_plan", "limitations"]:
        report += "\n\n" + (ROOT/f"docs/{name}.md").read_text()
    report += "\n\n## Реестр внешних источников\n\n"
    for s in sources.to_dict("records"):
        link = f"[{s['title']}]({s['url']})" if str(s['url']).startswith("http") else s['title']
        report += f"- [{s['source_id']}] {s['publisher']}. {link}. Публикация: {s.get('published') or 'не указана'}. Проверено {s['checked']}; статус {s['availability']}. {s['supports']}.\n"
    report += "\n\n## Использование ИИ\n\nCodex использован для реализации расчётного кода, подготовки черновиков, дизайна материалов и локальных проверок. Все выполненные проверки и их пределы перечислены в docs/qa_summary.md. Команда должна проверить смысл выводов и заполнить авторство. Интервью и результаты A/B-теста не создавались.\n"
    (d/"report.md").write_text(report)
    pdf_from_markdown(report, d/"report.pdf", run_id, figures=Path(run_dir)/"figures", title="От интереса к заказу — исследование", author=team.get('name') or 'Команда', draft=not team_ready)

    appendix = f"# Приложение к решению\n\nRun: `{run_id}`. Источник: текущий XLSX, сентябрь 2026. Числа ниже не заменяют определения и ограничения основного отчёта.\n\n"
    appendix += "## Аудит\n\n" + md_table(
        [(r.check_id, number(r.actual), number(r.reference), r.analysis_policy) for r in audit.itertuples()],
        ["Проверка", "Наблюдение", "Ориентир", "Правило анализа"])
    appendix += "\n\n## Тематики товарной базы\n\n" + md_table(
        [(r.theme, r.n, r.sellers, r.candidates) for r in tables["themes"].sort_values("candidates", ascending=False).itertuples()],
        ["Тема", "База", "С заказами", "Кандидаты"])
    appendix += "\n\n## Устойчивость\n\n" + md_table(
        [(r.variant, r.n, number(r.seller_share*100,2)+"%", number(r.aov,2)) for r in tables["robustness"].itertuples()],
        ["Вариант", "База", "С заказами / база", "ΣGMV / Σзаказов, ₽"])
    appendix += "\n\n## Парный анализ контента\n\n" + md_table(
        [(r.comparison, r.n, number(r.median,6), f"{number(r.ci_low,6)} … {number(r.ci_high,6)}") for r in tables["content_comparisons"].itertuples()],
        ["Описательная величина", "Бизнесы", "Медиана", "Bootstrap 95%"])
    appendix += "\n\n## Утверждения и ограничения\n\n"
    for r in claims.itertuples():
        appendix += f"### {r.claim_id} · {r.type}\n\n{r.text}\n\nОграничение: {r.limitation} Проверка: {r.status}. Решение: {r.decision_implication}\n\n"
    appendix += "\n\n" + (ROOT/"docs/team_workplan.md").read_text()
    (d/"appendix.md").write_text(appendix)
    pdf_from_markdown(appendix, d/"appendix.pdf", run_id, title="Приложение: аудит и доказательства", author=team.get('name') or 'Команда', draft=not team_ready)
    (d/"report_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False))
