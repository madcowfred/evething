import sqlite3


def main():
	# Connect databases
	inconn = sqlite3.connect('tyr10-sqlite3-v1.db')
	incur = inconn.cursor()
	
	outconn = sqlite3.connect('everdi.db')
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
	incur.execute('SELECT typeID, typeName, portionSize FROM invTypes')
	for row in incur:
		outcur.execute("INSERT INTO rdi_item (id, name, portion_size, sell_median, buy_median) VALUES (?, ?, ?, 0, 0)", row)
	outconn.commit()
	
	# Blueprints
	incur.execute("""
SELECT b.blueprintTypeID, t.typeName, b.productTypeID, b.productionTime, b.productivityModifier, b.materialModifier, b.wasteFactor
FROM invBlueprintTypes AS b
  INNER JOIN invTypes AS t
    ON b.blueprintTypeID = t.typeID
WHERE t.published = 1
""")
	bprows = incur.fetchall()
	for bprow in bprows:
		outcur.execute("""
INSERT INTO rdi_blueprint
(id, name, item_id, production_time, productivity_modifier, material_modifier, waste_factor)
VALUES
(?, ?, ?, ?, ?, ?, ?)
""", bprow)
		
		# Base materials
		incur.execute('SELECT materialTypeID, quantity FROM invTypeMaterials WHERE typeID=?', (bprow[2],))
		for baserow in incur:
			outcur.execute("""
INSERT INTO rdi_blueprintcomponent
(blueprint_id, item_id, count, needs_waste)
VALUES
(?, ?, ?, 1)
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
INSERT INTO rdi_blueprintcomponent
(blueprint_id, item_id, count, needs_waste)
VALUES
(?, ?, ?, 0)
""", (bprow[0], extrarow[0], extrarow[1]))
	
	outconn.commit()


if __name__ == '__main__':
	main()
