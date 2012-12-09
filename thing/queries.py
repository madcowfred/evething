# 
corporation_wallets = """
SELECT  cw.corporation_id, c.name, cw.account_key, cw.description, cw.balance
FROM    thing_corpwallet cw
INNER JOIN thing_corporation c ON c.id = cw.corporation_id
WHERE   corporation_id IN (
    SELECT  DISTINCT c.corporation_id
    FROM    thing_character c
    INNER JOIN thing_apikey ak ON c.apikey_id = ak.id
    WHERE ak.user_id = %s
)
ORDER BY c.name, cw.account_key
"""

order_aggregation = """
SELECT  mo.character_id,
        c.name,
        COUNT(mo.order_id) AS orders,
        COALESCE(SUM(CASE WHEN mo.corp_wallet_id IS NULL THEN 1 END), 0) AS personal_orders,
        COALESCE(SUM(CASE WHEN mo.corp_wallet_id IS NOT NULL THEN 1 END), 0) AS corp_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN true THEN 1 END), 0) AS buy_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN true THEN mo.total_price END), 0) AS total_buys,
        COALESCE(SUM(CASE mo.buy_order WHEN false THEN 1 END), 0) AS sell_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN false THEN mo.total_price END), 0) AS total_sells,
        COALESCE(SUM(mo.escrow), 0) AS total_escrow
FROM    thing_marketorder mo, thing_character c, thing_apikey_characters ac, thing_apikey a
WHERE   mo.character_id = c.id
        AND c.id = ac.character_id
        AND ac.apikey_id = a.id
        AND a.user_id = %s
GROUP BY mo.character_id, c.name
ORDER BY c.name
"""

# BPCalc movement calculation
bpcalc_movement = """
SELECT  item_id, CAST(SUM(movement) / 30 * %%s AS decimal(18,2))
FROM    thing_pricehistory
WHERE   item_id IN (%s)
        AND date >= %%s
GROUP BY item_id
"""

# item_ids for a specific user's BlueprintInstance objects and related components
user_item_ids = """
SELECT  bp.item_id
FROM    thing_blueprint bp, thing_blueprintinstance bpi
WHERE   bp.id = bpi.blueprint_id
        AND bpi.user_id = %s
UNION
SELECT  item_id
FROM    thing_blueprintcomponent
WHERE   blueprint_id IN (
            SELECT  blueprint_id
            FROM    thing_blueprintinstance
            WHERE   user_id = %s
)
UNION
SELECT  ca.item_id
FROM    thing_asset ca, thing_character c, thing_apikey_characters ac, thing_apikey a,
        thing_item i, thing_itemgroup ig
WHERE   ca.character_id = c.id
        AND c.id = ac.character_id
        AND ac.apikey_id = a.id
        AND a.user_id = %s
        AND ca.item_id = i.id
        AND i.item_group_id = ig.id
        AND ig.category_id != 9
"""

# item_ids for all BlueprintInstance objects and related components
all_item_ids = """
SELECT  bp.item_id
FROM    thing_blueprint bp, thing_blueprintinstance bpi
WHERE   bp.id = bpi.blueprint_id
UNION
SELECT  item_id
FROM    thing_blueprintcomponent
WHERE   blueprint_id IN (
            SELECT  blueprint_id
            FROM    thing_blueprintinstance
)
UNION
SELECT  a.item_id
FROM    thing_asset a, thing_item i, thing_itemgroup ig
WHERE   a.item_id = i.id
        AND i.item_group_id = ig.id
        AND ig.category_id != 9
"""


# 
journal_aggregate_char = """
SELECT  EXTRACT(YEAR FROM date) AS year,
        EXTRACT(MONTH FROM date) AS month,
        EXTRACT(DAY FROM date) AS day,
        ref_type_id,
        SUM(CASE WHEN (amount > 0) THEN amount ELSE 0 END) AS income,
        SUM(CASE WHEN (amount < 0) THEN amount ELSE 0 END) as expense
FROM    thing_journalentry
WHERE   character_id = %s
        AND corp_wallet_id IS NULL
GROUP BY year, month, day, ref_type_id
"""

journal_aggregate_corp = """
SELECT  EXTRACT(YEAR FROM date) AS year,
        EXTRACT(MONTH FROM date) AS month,
        EXTRACT(DAY FROM date) AS day,
        ref_type_id,
        SUM(CASE WHEN (amount > 0) THEN amount ELSE 0 END) AS income,
        SUM(CASE WHEN (amount < 0) THEN amount ELSE 0 END) as expense
FROM    thing_journalentry
WHERE   character_id = %s
        AND corp_wallet_id = %s
GROUP BY year, month, day, ref_type_id
"""


# taskmeta stuff
task_summary_generic = """
SELECT  EXTRACT(YEAR FROM date_done) AS y,
        EXTRACT(MONTH FROM date_done) AS m,
        EXTRACT(DAY FROM date_done) AS d,
        EXTRACT(HOUR FROM date_done) AS h,
        COUNT(*) AS count
FROM    celery_taskmeta
GROUP BY y, m, d, h
ORDER BY y, m, d, h
"""

task_summary_sqlite = """
SELECT  strftime('%Y', date_done) as y,
        strftime('%m', date_done) as m,
        strftime('%d', date_done) as d,
        strftime('%H', date_done) as h,
        COUNT(*) AS count
FROM    celery_taskmeta
GROUP BY y, m, d, h
ORDER BY y, m, d, h
"""
