"""Traceable claims: observation, limitation, decision, validation owner."""

import pandas as pd


def claims(metrics, scenarios, comparisons):
    m = metrics
    base = scenarios[scenarios.name == "Базовый"].iloc[0] if "Базовый" in scenarios.name.values else scenarios.iloc[0]
    rows = [
        ("C01", f"Из {m['goods_businesses']} товарных/смешанных бизнесов {m['selling_goods']} имеют внутренние заказы; доля {m['seller_share']*100:.2f}%.",
         "dataset_fact", "goods_businesses;selling_goods;seller_share", "DATA", "verified",
         "Синтетическая выборка; продажи вне чекаута не наблюдаются.", "Проверять путь до первого внутреннего заказа."),
        ("C02", f"Фильтру кандидатов соответствуют {m['candidates']} бизнесов.", "dataset_fact", "candidates", "DATA", "verified",
         "Это не потерянные клиенты и не гарантированные новые продавцы.", "Ручная квалификация и аудит перед пилотом."),
        ("C03", f"По темам хендмейда и хобби — {m['candidates_handmade']+m['candidates_hobby']} кандидатов; еды — {m['candidates_food']}.",
         "dataset_fact", "candidates_handmade;candidates_hobby;candidates_food", "DATA", "verified",
         "Тема не подтверждает ассортимент и локальность.", "Приоритет А, затем Б; подтвердить сегмент интервью."),
        ("C04", f"Главная даёт {m['homepage_share']*100:.3f}% открытий карточек товаров Маркета.", "dataset_fact",
         "homepage_opens;market_opens;homepage_share", "DATA", "verified",
         "Нет заказов и затрат по поверхности; малая доля не доказывает убыточность.", "Проверять главную отдельным пользовательским экспериментом."),
        ("C05", f"Заказы категорий Маркета {m['market_category_orders']:.0f} отличаются от итога {m['market_orders']:.0f}.",
         "dataset_fact", "market_category_orders;market_orders", "DATA", "verified",
         "Причина неизвестна.", "Не подгонять; распределение считать от суммы разреза."),
        ("C06", f"Взвешенный чек товарной базы — {m['goods_aov']:.6f} ₽.", "dataset_fact", "goods_aov;goods_gmv;goods_orders",
         "DATA", "verified", "GMV до возвратов; состав заказов сценария может отличаться.", "Использовать неокруглённый чек и проверить чувствительность."),
        ("C07", f"У {m['original_missing']} бизнесов отсутствует оценка оригинальности.", "dataset_fact", "original_missing;businesses",
         "DATA", "verified", "Оценка модели не истинная метка.", "Не делать оригинальность обязательным фильтром."),
        ("C08", f"Десять крупнейших товарных бизнесов дают {m['gmv_top_10_share']*100:.2f}% GMV товарной базы.",
         "dataset_fact", "gmv_top_10_share;goods_gmv", "DATA", "verified", "Один месяц и синтетическая выборка.",
         "Проверять выводы без экстремальных наблюдений."),
        ("H01", "Единый путь с ясными условиями увеличит долю продающих бизнесов.", "hypothesis", "", "C01;C02", "untested",
         "Барьер может оказаться в спросе, наличии или исполнении.", "Качественный пилот и затем рандомизированный тест."),
        ("I01", "Маркет целесообразно развивать как общие торговые компоненты с проверкой отдельной главной.", "interpretation",
         "homepage_share", "C01;C04;VK1", "reasoned_not_causal", "Доступность переиспользования и стоимость неизвестны.",
         "Сравнить четыре альтернативы; пересмотреть при доказанном вкладе главной."),
        ("S01", f"Базовый сценарий: {base.delta_sellers:.2f} дополнительных продавца и {base.gmv_realized:.2f} ₽ сохранённой стоимости.",
         "scenario", "candidates;goods_aov", "DATA;config/project.yaml", "calculated_assumptions",
         "Активация, частота, исполнение и монетизация заданы, эффект не измерен.", "Не обещать рост; проверить параметры пилотом."),
        ("E01", "Шопсы и реферальная программа уже существуют на базе VK AdBlogger.", "external_fact", "", "VK1", "primary_source_opened",
         "Заявление компании; не причинный эксперимент для самостоятельных бизнесов.", "Использовать текущие компоненты, проверить доступность продавцам."),
        ("E02", "Расходы Ozon зависят от схемы и категории, помимо вознаграждения есть другие статьи.", "external_fact", "", "OZ1",
         "primary_source_opened", "Точные ставки конкретного товара не применены к модели.", "Сравнивать полную экономику каналов."),
        ("D01", "Локальный прототип показывает создание и статусы заказа с дедупликацией.", "demo", "", "data/demo", "local_implementation",
         "Не интегрирован с VK и не доказывает рост.", "Проверить понимание пути до разработки."),
    ]
    if not comparisons.empty:
        r = comparisons.iloc[0]
        interval_note = "включает ноль" if r.ci_low <= 0 <= r.ci_high else "не включает ноль"
        rows.append(("C09", f"Парный анализ просмотров на публикацию доступен для {int(r['n'])} бизнесов; интервал лог-отношения {interval_note}.",
                     "dataset_fact", "content_comparisons", "DATA", "verified",
                     "Трактовка числа обычных публикаций требует подтверждения; малая доступная подбаза.",
                     "Не обосновывать универсальное ухудшение охватов по этому анализу."))
    cols = ["claim_id", "text", "type", "metric_ids", "source_ids", "status", "limitation", "decision_implication"]
    df = pd.DataFrame(rows, columns=cols)
    df["owner_role"] = "аналитик / стратегия"
    df["reviewer_role"] = "капитан / экономика"
    return df
