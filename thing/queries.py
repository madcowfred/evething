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
        COUNT(mo.*) AS orders,
        COALESCE(SUM(CASE WHEN mo.corp_wallet_id IS NULL THEN 1 END), 0) AS personal_orders,
        COALESCE(SUM(CASE WHEN mo.corp_wallet_id IS NOT NULL THEN 1 END), 0) AS corp_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN true THEN 1 END), 0) AS buy_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN true THEN mo.total_price END), 0) AS total_buys,
        COALESCE(SUM(CASE mo.buy_order WHEN false THEN 1 END), 0) AS sell_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN false THEN mo.total_price END), 0) AS total_sells,
        COALESCE(SUM(mo.escrow), 0) AS total_escrow
FROM    thing_marketorder mo, thing_character c, thing_apikey ak
WHERE   mo.character_id = c.eve_character_id
        AND c.apikey_id = ak.id
        AND ak.user_id = %s
GROUP BY mo.character_id, c.name
ORDER BY c.name
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
"""

# This is the nasty trade timeframe thing. Be afraid.
# I hope one day I can do this via the Django ORM :p
trade_timeframe = """
SELECT
  COALESCE(t1.item_id, t2.item_id) AS id,
  i.name,
  ic.name AS cat_name,
  i.sell_price,
  t1.buy_maximum, t1.buy_quantity, t1.buy_total, t1.buy_minimum,
  t2.sell_maximum, t2.sell_quantity, t2.sell_total, t2.sell_minimum,
  t1.buy_total / t1.buy_quantity AS buy_average,
  t2.sell_total / t2.sell_quantity AS sell_average,
  COALESCE(t2.sell_total, 0) - COALESCE(t1.buy_total, 0) AS balance,
  t1.buy_quantity - t2.sell_quantity AS diff
FROM
(
  %s
) t1
FULL OUTER JOIN
(
  %s
) t2
ON t1.item_id = t2.item_id
INNER JOIN thing_item i
ON i.id = COALESCE(t1.item_id, t2.item_id)
INNER JOIN thing_itemgroup ig
ON i.item_group_id = ig.id
INNER JOIN thing_itemcategory ic
ON ig.category_id = ic.id
"""
