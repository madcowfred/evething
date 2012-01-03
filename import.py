import psycopg2
import settings
import sqlite3
import sys
import time


def main():
    # Connect databases
    inconn = sqlite3.connect('cruc101-sqlite3-v1.db')
    incur = inconn.cursor()
    
    #outconn = sqlite3.connect('evething.db')
    #outcur = outconn.cursor()
    outconn = psycopg2.connect('dbname=%(NAME)s user=%(USER)s' % (settings.DATABASES['default'])) 
    outcur = outconn.cursor()
    
    # Regions
    # regionID,regionName,x,y,z,xMin,xMax,yMin,yMax,zMin,zMax,factionID,radius
    #incur.execute('SELECT regionID, regionName FROM mapRegions WHERE regionName != "Unknown"')
    #for row in incur:
    #    outcur.execute("INSERT INTO blueprints_region (id, name) VALUES (%s, %s)", row)
    #outconn.commit()
    
    # Categories
    t = time.time()
    print '=> Importing ItemCategory...',
    sys.stdout.flush()
    incur.execute('SELECT categoryID, categoryName FROM invCategories')
    for row in incur:
        if row[0] and row[1]:
            outcur.execute('INSERT INTO thing_itemcategory (id, name) VALUES (%s, %s)', row)
    outconn.commit()
    print '%.1fs' % (time.time() - t)
    
    # Groups
    t = time.time()
    print '=> Importing ItemGroup...',
    sys.stdout.flush()
    incur.execute('SELECT groupID, groupName, categoryID FROM invGroups')
    for row in incur:
        if row[2]:
            outcur.execute('INSERT INTO thing_itemgroup (id, name, category_id) VALUES (%s, %s, %s)', row)
    outconn.commit()
    print '%.1fs' % (time.time() - t)
    
    # Items
    # typeID,groupID,typeName,description,graphicID,radius,mass,volume,capacity,portionSize,raceID,basePrice,published,
    #   marketGroupID,chanceOfDuplicating
    t = time.time()
    print '=> Importing Item...',
    sys.stdout.flush()
    incur.execute('SELECT typeID, typeName, groupID, portionSize, volume FROM invTypes')
    for row in incur:
        if row[2]:
            outcur.execute("INSERT INTO thing_item (id, name, group_id, portion_size, volume, sell_price, buy_price) VALUES (%s, %s, %s, %s, %s, 0, 0)", row)
    outconn.commit()
    print '%.1fs' % (time.time() - t)
    
    # Blueprints
    t = time.time()
    print '=> Importing Blueprint/BlueprintComponent...',
    sys.stdout.flush()
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
INSERT INTO thing_blueprint
(id, name, item_id, production_time, productivity_modifier, material_modifier, waste_factor)
VALUES
(%s, %s, %s, %s, %s, %s, %s)
""", bprow)
        
        # Base materials
        incur.execute('SELECT materialTypeID, quantity FROM invTypeMaterials WHERE typeID=?', (bprow[2],))
        for baserow in incur:
            outcur.execute("""
INSERT INTO thing_blueprintcomponent
(blueprint_id, item_id, count, needs_waste)
VALUES
(%s, %s, %s, true)
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
INSERT INTO thing_blueprintcomponent
(blueprint_id, item_id, count, needs_waste)
VALUES
(%s, %s, %s, false)
""", (bprow[0], extrarow[0], extrarow[1]))
    
    outconn.commit()
    print '%.1fs' % (time.time() - t)


if __name__ == '__main__':
    main()
