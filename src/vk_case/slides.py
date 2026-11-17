"""A shared positioned source exports exactly eight vector slides and editable PPTX."""

import json
from html import escape
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from .reporting import number, register_fonts

INK, BLUE, MUTED, LIGHT, PALE, WHITE = "#15263E", "#1768F2", "#61718A", "#F5F7FB", "#E5EDFA", "#FFFFFF"
W, H = 960, 540


def build_source(m, config, scenarios, experiment, run_id):
    slides = []
    team = config["team"]
    names = team.get("members") or [None]*4
    universities = team.get("universities") or [""]*4
    draft = not (team.get("name") and team.get("city") and len(names) == 4 and all(names))
    base = scenarios[scenarios.name == "Базовый"].iloc[0] if "Базовый" in scenarios.name.values else scenarios.iloc[0]

    def new(kicker, title, source="DATA · сентябрь 2026", dark=False):
        slide = {"background": INK if dark else LIGHT, "elements": [], "kicker": kicker, "source": source}
        slides.append(slide)
        text(44, 25, 820, 18, kicker.upper(), 10, "#A7B9D7" if dark else MUTED, True)
        rect(44, 52, 26, 3, BLUE)
        if title:
            text(44, 75, 870, 83, title, 31, WHITE if dark else INK, True)
        text(44, 510, 780, 13, f"{source}  ·  run {run_id}" + ("  ·  черновик" if draft else ""), 7.3,
             "#A7B9D7" if dark else MUTED)
        text(875, 507, 42, 18, f"{len(slides):02} / 08", 9, "#A7B9D7" if dark else MUTED)
        return slide

    def text(x, y, w, h, value, size=15, color=INK, bold=False):
        slides[-1]["elements"].append({"type": "text", "x": x, "y": y, "w": w, "h": h,
                                      "text": str(value), "size": size, "color": color, "bold": bold})

    def rect(x, y, w, h, color, radius=0):
        slides[-1]["elements"].append({"type": "rect", "x": x, "y": y, "w": w, "h": h,
                                      "color": color, "radius": radius})

    def line(x, y, x2, y2, color=PALE, width=1):
        slides[-1]["elements"].append({"type": "line", "x": x, "y": y, "x2": x2, "y2": y2,
                                      "color": color, "width": width})

    def metric(x, y, w, value, label, blue=False):
        rect(x, y, w, 108, BLUE if blue else WHITE, 12)
        text(x+20, y+15, w-40, 45, value, 34, WHITE if blue else INK, True)
        text(x+20, y+69, w-40, 30, label, 11.5, WHITE if blue else MUTED)

    new("VK Case Champ 2026 · исследовательская концепция", "", "Условия, стр. 20–21; DATA", True)
    text(44, 112, 565, 152, "От интереса\nк заказу", 57, WHITE, True)
    text(47, 289, 510, 72, "Помочь товарному бизнесу превратить\nдоверие к контенту в понятную покупку.", 20, "#CED9EA")
    rect(44, 404, 535, 54, "#233B5C", 9)
    text(60, 418, 507, 30, f"{team.get('name') or 'Название команды — заполнить'} · {team.get('city') or 'город — заполнить'}", 12, WHITE)
    rect(635, 119, 280, 338, "#203750", 18)
    text(657, 144, 235, 26, "ПУТЬ ПРОДАВЦА", 11, "#A7B9D7", True)
    for y, num, title, subtitle in [(192, "01", "Есть интерес", "Контент и активный каталог"),
                                    (276, "02", "Ясны условия", "Товар, получение и оплата"),
                                    (360, "03", "Есть заказ", "Подтверждение и исполнение")]:
        rect(657, y, 34, 34, BLUE if num == "03" else "#355071", 9)
        text(664, y+8, 25, 20, num, 12, WHITE, True)
        text(705, y-1, 185, 24, title, 17, WHITE, True)
        text(705, y+29, 183, 32, subtitle, 10.5, "#A7B9D7")
        if num != "03":
            line(674, y+42, 674, y+72, "#496381", 1.5)

    new("Команда · WW team · Санкт-Петербург", "Четыре участника —\nединое решение", "Состав предоставлен командой · распределение ролей предложено для согласования")
    roles = [("Капитан / стратегия", "Пять ответов кейса, альтернативы,\nединая логика решения."),
             ("Аналитик", "Семь листов, аудит, сегменты,\nнезависимая сверка чисел."),
             ("Исследователь / продукт", "Интервью, аудит путей,\nпроверка барьера и макетов."),
             ("Экономика / редактор", "Допущения, эксперимент, риски,\nсведение материалов защиты.")]
    for i, (role, description) in enumerate(roles):
        x, y = 44 + (i % 2)*444, 174 + (i // 2)*149
        rect(x, y, 428, 132, WHITE, 12)
        text(x+18, y+13, 36, 24, f"0{i+1}", 15, BLUE, True)
        text(x+64, y+13, 340, 26, names[i] or f"Участник {i+1} — имя не указано", 15, INK, True)
        text(x+64, y+43, 340, 16, universities[i], 10, MUTED)
        text(x+64, y+65, 340, 21, role, 12, BLUE, True)
        text(x+64, y+94, 340, 30, description, 10.5, MUTED)
    text(44, 478, 870, 20, f"{team.get('name') or 'Команда не указана'} · {team.get('city') or 'город не указан'} · ИИ: Codex — код, черновики, дизайн и локальные проверки; требуется проверка команды.", 9, MUTED)

    new("Резюме решения", "Проверить путь до первой продажи", "DATA · Бизнесы; сценарий — config/project.yaml")
    metric(44, 163, 276, number(m["goods_businesses"]), "товарных и смешанных бизнесов")
    metric(334, 163, 276, f"{number(m['seller_share']*100,2)}%", f"с заказами: {number(m['selling_goods'])} / {number(m['goods_businesses'])}")
    metric(624, 163, 291, number(m["candidates"]), "кандидатов для проверки пути", True)
    text(47, 298, 500, 26, "Кому и что предлагаем", 20, INK, True)
    text(47, 341, 490, 109, "Сначала мастерские и небольшие бренды.\nЯсная карточка → условия → подтверждение.\nМаркет — общие торговые компоненты.\nЛокальная еда — следующий маршрут.", 16, INK)
    rect(587, 298, 328, 170, PALE, 12)
    text(607, 316, 290, 24, "ГИПОТЕЗА, КОТОРУЮ ПРОВЕРЯЕМ", 10, BLUE, True)
    text(607, 352, 280, 48, f"+{number(base.delta_sellers,2)}", 36, INK, True)
    text(607, 409, 280, 45, "продавца в базовом сценарии.\nЭто ожидание, а не результат теста.", 12, MUTED)
    text(47, 478, 850, 19, "Главный исход: уникальные подходящие бизнесы с ≥1 внутренним заказом за 30 дней; отдельно — выполнение.", 10, MUTED)

    new("Диагностика · факт и ограничение", "Готовность видна.\nПричину отсутствия заказов надо проверить.", "DATA · Бизнесы; Источники; Итоги; Категории")
    labels = [("Товарная база", m['goods_businesses'], PALE), ("Есть заказы", m['selling_goods'], BLUE),
              ("Кандидаты", m['candidates'], INK)]
    for y, (label, value, color) in zip([205, 289, 373], labels, strict=True):
        text(47, y-20, 330, 21, label, 12, MUTED)
        rect(47, y+9, 418*value/m['goods_businesses'], 25, color, 4)
        text(483, y+6, 80, 35, number(value), 20, INK, True)
    text(47, 449, 500, 31, "Группы пересекаются. Это не последовательная воронка.", 10, MUTED)
    rect(600, 184, 315, 295, WHITE, 12)
    text(619, 204, 276, 34, f"{number(m['homepage_share']*100,3)}%", 28, BLUE, True)
    text(619, 246, 276, 49, "открытий товаров Маркета — с главной.\nНет данных о её заказах и затратах.", 12, MUTED)
    line(619, 307, 895, 307)
    text(619, 327, 276, 35, f"+{number(m['market_category_orders']-m['market_orders'])}", 27, INK, True)
    text(619, 368, 276, 81, "заказов в категориях сверх итога.\nПричина неизвестна. Разрезы не подгоняем; интервалы контентного анализа не доказывают общего падения охватов.", 12, MUTED)

    new("Альтернативы · одна рамка сравнения", "Развивать торговый слой,\nприоритет главной решать экспериментом", "DATA · источники; VK1; OZ1; аналитические оценки, без числовых баллов")
    alternatives = [
        ("01", "Самостоятельная витрина", "Новый вход и большой ассортимент.\nСпрос, стоимость и вклад не доказаны.", False),
        ("02", "Общие товарные компоненты", "Путь из контента и сообщества.\nПрямо отвечает цели внутренних заказов.", True),
        ("03", "Внешний партнёрский путь", "Подходит внешнему продавцу.\nДоход возможен, внутренний KPI отдельно.", False),
        ("04", "Меньше инвестиций в главную", "Сохранить карточки и оформление.\nЭкономию и переток ещё надо измерить.", False),
    ]
    for i, (num, title, body, selected) in enumerate(alternatives):
        x, y = 44+(i % 2)*444, 180+(i // 2)*136
        rect(x, y, 428, 120, BLUE if selected else WHITE, 12)
        text(x+18, y+17, 30, 20, num, 11, WHITE if selected else BLUE, True)
        text(x+58, y+15, 352, 28, title, 17, WHITE if selected else INK, True)
        text(x+58, y+58, 350, 50, body, 12.5, WHITE if selected else MUTED)
    text(47, 467, 865, 29, "VK дополняет поиск сформированного спроса: доверие, понятное предложение, связь с клиентом. Стоимость продажи требует полной экономики.", 11, MUTED)

    new("Концепция · один пакет, разные маршруты", "От ясного предложения\nк подтверждённому заказу", "Целевой дизайн · не описание действующего API VK; VK1 — карточки в контенте")
    steps = [("Диагностика", "Один следующий шаг"), ("Предложение", "Наличие, цена, срок"),
             ("Получение", "Условия и оплата"), ("Заказ", "Подтверждение и статус")]
    for i, (title, body) in enumerate(steps):
        x = 44+i*223
        rect(x, 185, 206, 91, BLUE if i == 3 else WHITE, 10)
        text(x+16, 201, 176, 25, title, 17, WHITE if i == 3 else INK, True)
        text(x+16, 239, 176, 29, body, 10.5, WHITE if i == 3 else MUTED)
        if i < 3:
            text(x+208, 216, 16, 24, "→", 13, BLUE)
    branches = [("Стандартный товар", "Карточка → условия → заказ", "Наличие и способ получения до подтверждения."),
                ("Товар под заказ", "Запрос → предложение → согласие", "Заказ создаётся после согласования условий."),
                ("Локальная еда", "Зона → время → самовывоз", "Недоступная зона блокирует подтверждение.")]
    for i, (title, path, note) in enumerate(branches):
        x = 44+i*296
        rect(x, 309, 280, 128, WHITE, 10)
        text(x+16, 324, 247, 26, title, 16, INK, True)
        text(x+16, 360, 247, 37, path, 11.5, BLUE)
        text(x+16, 402, 247, 30, note, 10, MUTED)
    text(47, 461, 865, 31, "Внешний переход учитывается отдельно. Онлайн-оплата и оплата при получении имеют разные допустимые состояния заказа.", 11, MUTED)

    new("Обоснование · сценарий, не прогноз", "Малый пилот проверяет механизм.\nОкупаемость ещё нужно доказать.", "DATA · N и AOV; config/project.yaml · остальные параметры — допущения")
    table_x = [44, 365, 548, 731]
    text(44, 177, 290, 20, "Параметр / ожидание", 10, MUTED, True)
    for x, spec in zip(table_x[1:], scenarios.iloc[:3].to_dict('records'), strict=True):
        text(x, 173, 160, 24, spec['name'], 16, BLUE, True)
    rows = [("Дополнительная активация", lambda r: f"+{number(r['delta_activation']*100)} п.п."),
            ("Заказов на доп. продавца", lambda r: number(r['orders_per_seller'])),
            ("Дополнительные продавцы", lambda r: number(r['delta_sellers'],2)),
            ("Сохранённая стоимость", lambda r: number(r['gmv_realized'])+" ₽")]
    for i, (label, get_value) in enumerate(rows):
        y = 219+i*42
        line(44, y-9, 915, y-9)
        text(44, y, 310, 27, label, 13, INK, i == 3)
        for x, spec in zip(table_x[1:], scenarios.iloc[:3].to_dict('records'), strict=True):
            text(x, y, 172, 27, get_value(spec), 14, INK, i == 3)
    rect(44, 397, 871, 85, INK, 10)
    text(61, 411, 520, 56, f"N={number(m['candidates'])} · AOV={number(m['goods_aov'],2)} ₽\n2% — условная ставка; инвестиции {number(config['economics']['investment'])} ₽ — пример сметы.", 12, WHITE)
    margin_note = "Прибыль продавца недоступна." if config['economics']['gross_margin'] is None else "Прибыль зависит от допущений."
    payback_note = f"Окупаемость: {int(base.payback_month)} мес." if base.payback_month == base.payback_month and base.payback_month is not None else f"Окупаемость за {config['economics']['horizon_months']} мес. не достигается."
    text(618, 411, 277, 61, f"Затраты требуют подтверждения.\n{margin_note}\n{payback_note}", 11.5, "#CED9EA")

    new("Рекомендация · проверка перед масштабом", "Сначала доказать дополнительный\nзаказ и пользу обеим сторонам", "Проектный дизайн · причинный эффект неизвестен; STAT · расчёт мощности")
    phases = [("01", "Проверить барьер", "8 интервью, 12 аудитов,\n4 покупательских теста.\nСтатус: не проведены."),
              ("02", "Технический пилот", "20–30 продавцов.\nПуть, статусы, события,\nкачество исполнения."),
              ("03", "Причинный тест", f"По бизнесам, ITT, 30 дней.\nИллюстрация: {number(experiment['n_control'])} на группу\nдля {number(experiment['mde_pp'],1)} п.п.; p0={number(experiment['p0']*100,2)}%."),
              ("04", "Решение о росте", "Прибыль продавца и вклад VK.\nОтдельно — тест главной,\nс учётом перетока.")]
    for i, (num, title, body) in enumerate(phases):
        x = 44+i*223
        rect(x, 181, 206, 181, BLUE if i == 2 else WHITE, 12)
        text(x+16, 197, 170, 30, num, 22, WHITE if i == 2 else BLUE, True)
        text(x+16, 244, 174, 37, title, 14, WHITE if i == 2 else INK, True)
        text(x+16, 290, 174, 62, body, 10.6, WHITE if i == 2 else MUTED)
    text(47, 392, 855, 40, "Главная метрика — продающие бизнесы. Защитные — выполнение, отмены, возвраты, жалобы и прибыль.", 15, INK, True)
    sample_note = "Набора недостаточно" if m['candidates'] < experiment['n_total'] else "Набор формально достаточен при допущениях"
    text(47, 445, 850, 47, f"{number(m['candidates'])} кандидатов. {sample_note} для показанного MDE. Пересмотреть концепцию при перетоке, отсутствии прибыли продавца или ухудшении исполнения. Часовой пояс сдачи требует подтверждения.", 11, MUTED)
    return {"run_id": run_id, "draft": draft, "team": team, "size": [W, H], "metrics": m, "slides": slides}


def export_slides(run_dir, source):
    register_fonts()
    d = Path(run_dir)/"slides"
    d.mkdir(exist_ok=True)
    (d/"slides_source.json").write_text(json.dumps(source, ensure_ascii=False, indent=2, allow_nan=False))
    canvas = Canvas(str(d/"strategy_draft.pdf"), pagesize=(W, H))
    canvas.setTitle("WW team · От интереса к заказу · VK Case Champ 2026" + (" · черновик" if source["draft"] else ""))
    canvas.setAuthor(source["team"].get("name") or "Команда")
    presentation = Presentation()
    presentation.core_properties.author = source["team"].get("name") or "Команда"
    presentation.core_properties.title = "WW team · От интереса к заказу"
    presentation.slide_width, presentation.slide_height = Inches(W/72), Inches(H/72)
    checks = []
    for i, slide in enumerate(source["slides"], start=1):
        canvas.setFillColor(HexColor(slide["background"]))
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        page = presentation.slides.add_slide(presentation.slide_layouts[6])
        page.background.fill.solid()
        page.background.fill.fore_color.rgb = RGBColor.from_string(slide["background"].lstrip("#"))
        for j, e in enumerate(slide["elements"]):
            if e["type"] == "rect":
                canvas.setFillColor(HexColor(e["color"]))
                canvas.roundRect(e["x"], H-e["y"]-e["h"], e["w"], e["h"], e["radius"], fill=1, stroke=0)
                shape = page.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if e["radius"] else MSO_SHAPE.RECTANGLE,
                                               Pt(e["x"]), Pt(e["y"]), Pt(e["w"]), Pt(e["h"]))
                if e["radius"]:
                    shape.adjustments[0] = min(.18, e["radius"]/min(e["w"], e["h"]))
                shape.fill.solid()
                shape.fill.fore_color.rgb = RGBColor.from_string(e["color"].lstrip("#"))
                shape.line.fill.background()
            elif e["type"] == "line":
                canvas.setStrokeColor(HexColor(e["color"]))
                canvas.setLineWidth(e["width"])
                canvas.line(e["x"], H-e["y"], e["x2"], H-e["y2"])
                shape = page.shapes.add_shape(MSO_SHAPE.RECTANGLE, Pt(e["x"]), Pt(e["y"]),
                                               Pt(max(e["width"], e["x2"]-e["x"])),
                                               Pt(max(e["width"], e["y2"]-e["y"])))
                shape.fill.solid()
                shape.fill.fore_color.rgb = RGBColor.from_string(e["color"].lstrip("#"))
                shape.line.fill.background()
            else:
                style = ParagraphStyle("slide", fontName="CaseBold" if e["bold"] else "Case",
                                       fontSize=e["size"], leading=e["size"]*1.22, textColor=HexColor(e["color"]))
                para = Paragraph(escape(e["text"]).replace("\n", "<br/>"), style)
                _, used_h = para.wrap(e["w"], H)
                fits = used_h <= e["h"]+.2 and e["y"]+used_h <= H and e["x"]+e["w"] <= W
                checks.append({"slide": i, "element": j, "fits": fits, "used_height": used_h,
                               "box_height": e["h"], "text": e["text"][:100]})
                if not fits:
                    raise ValueError(f"Переполнение слайда {i}, элемент {j}: {e['text'][:65]} ({used_h:.1f}>{e['h']})")
                para.drawOn(canvas, e["x"], H-e["y"]-used_h)
                shape = page.shapes.add_textbox(Pt(e["x"]), Pt(e["y"]), Pt(e["w"]), Pt(e["h"]+2))
                tf = shape.text_frame
                tf.word_wrap = True
                tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
                for k, part in enumerate(e["text"].split("\n")):
                    p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                    p.text = part
                    p.font.name, p.font.size, p.font.bold = "DejaVu Sans", Pt(e["size"]), e["bold"]
                    p.font.color.rgb = RGBColor.from_string(e["color"].lstrip("#"))
                    p.space_after = Pt(0)
                    p.space_before = Pt(0)
                    p.line_spacing = 1.22
        page.notes_slide.notes_text_frame.text = f"run {source['run_id']}. {slide['source']}. Источники, расчёты и ограничения — reports/report.pdf и reports/appendix.pdf. ИИ: Codex — код, черновики, дизайн, локальные проверки."
        canvas.showPage()
    canvas.save()
    presentation.save(str(d/"strategy_draft.pptx"))
    (d/"layout_checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2))
    return checks
