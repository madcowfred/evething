import psycopg2
import sqlite3


def main():
	# Connect databases
	inconn = sqlite3.connect('tyr10-sqlite3-v1.db')
	incur = inconn.cursor()
	
	outconn = psycopg2.connect("dbname='everdi' user='freddie' host='localhost'")
	outcur = outconn.cursor()
	
	# Regions
	# regionID,regionName,x,y,z,xMin,xMax,yMin,yMax,zMin,zMax,factionID,radius
	#incur.execute('SELECT regionID, regionName FROM mapRegions WHERE regionName != "Unknown"')
	#for row in incur:
	#	outcur.execute("INSERT INTO blueprints_region (id, name) VALUES (%s, %s)", row)
	#outconn.commit()
	
	# Items
	# typeID,groupID,typeName,description,graphicID,radius,mass,volume,capacity,portionSize,raceID,basePrice,published,
	#   marketGroupID,chanceOfDuplicating
	incur.execute('SELECT typeID, typeName FROM invTypes')
	for row in incur:
		outcur.execute("INSERT INTO blueprints_item (id, name, sell_median, buy_median) VALUES (%s, %s, 0, 0)", row)
	outconn.commit()
	
	# Blueprints
	incur.execute("""
SELECT b.blueprintTypeID, t.typeName, b.productTypeID, b.productionTime, b.productivityModifier, b.materialModifier, b.wasteFactor
FROM invBlueprintTypes AS b
  INNER JOIN invTypes AS t
    ON b.blueprintTypeID = t.typeID
""")
	bprows = incur.fetchall()
	for bprow in bprows:
		outcur.execute("""
INSERT INTO blueprints_blueprint
(id, name, item_id, production_time, productivity_modifier, material_modifier, waste_factor)
VALUES
(%s, %s, %s, %s, %s, %s, %s)
""", bprow)
		
		# Base materials
		incur.execute('SELECT materialTypeID, quantity FROM invTypeMaterials WHERE typeID=?', (bprow[2],))
		for baserow in incur:
			outcur.execute("""
INSERT INTO blueprints_blueprintcomponent
(blueprint_id, item_id, count, needs_waste)
VALUES
(%s, %s, %s, TRUE)
""", (bprow[0], baserow[0], baserow[1]))
		
		# Extra materials. activityID 1 is manufacturing - categoryID 16 is skill requirements
		incur.execute("""
SELECT r.requiredTypeID, r.quantity
FROM ramTypeRequirements AS r
  INNER JOIN invTypes AS t
    ON r.requiredTypeID = t.typeID
  INNER JOIN invGroups AS g
    ON t.groupID = g.groupID
WHERE r.typeID = ?
  AND r.activityID = 1
  AND g.categoryID <> 16
""", (bprow[0],))
		
		for extrarow in incur:
			outcur.execute("""
INSERT INTO blueprints_blueprintcomponent
(blueprint_id, item_id, count, needs_waste)
VALUES
(%s, %s, %s, FALSE)
""", (bprow[0], extrarow[0], extrarow[1]))
	
	outconn.commit()

"""
-- Extra materials
SELECT t.typeName, r.quantity, r.damagePerJob
FROM ramTypeRequirements AS r
 INNER JOIN invTypes AS t
  ON r.requiredTypeID = t.typeID
 INNER JOIN invGroups AS g
  ON t.groupID = g.groupID
WHERE r.typeID = 30467 -- Electromechanical Interface Nexus Blueprint
 AND r.activityID = 1 -- Manufacturing
 AND g.categoryID != 16; -- Skill
"""

"""
-- Base materials
SELECT t.typeName, m.quantity
FROM invTypeMaterials AS m
 INNER JOIN invTypes AS t
  ON m.materialTypeID = t.typeID
WHERE m.typeID = 27912; -- Concussion Bomb
 
-- Extra materials and skills
SELECT t.typeName, r.quantity, r.damagePerJob
FROM ramTypeRequirements AS r
 INNER JOIN invTypes AS t
  ON r.requiredTypeID = t.typeID
WHERE r.typeID = 27913 -- Concussion Bomb Blueprint
 AND r.activityID = 1; -- Manufacturing
 """


if __name__ == '__main__':
	main()
