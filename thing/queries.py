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

item_ids_nope = """
SELECT  item_id
FROM    thing_marketorder
UNION
"""

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
