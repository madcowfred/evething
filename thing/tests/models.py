from decimal import Decimal

from django.test import TestCase
from thing.models import *  # NOPEP8


class StationTestCase(TestCase):
    # fixtures = ['region_constellation_system_testdata.json']

    def setUp(self):
        super(StationTestCase, self).setUp()

        self.station1 = Station.objects.create(
            id=1,
            system_id=30000142,
            name='Jita IV - Moon 4 - Caldari Navy Assembly Plant',
        )

        self.station2 = Station.objects.create(
            id=2,
            system_id=30002904,
            name='VFK-IV VI - Moon river',
        )

    def test_make_shorter_name(self):
        self.assertEqual(self.station1.short_name, 'Jita 4-4 - CNAP')

        # Test weird station name
        self.assertEqual(self.station2.short_name, 'VFK-IV 6 - Mr')


class InventoryFlagTestCase(TestCase):
    fixtures = ['inventoryflag_testdata.json']

    def setUp(self):
        super(InventoryFlagTestCase, self).setUp()

        self.hi_slot_1 = InventoryFlag.objects.get(pk=27)
        self.med_slot_1 = InventoryFlag.objects.get(pk=19)
        self.low_slot_1 = InventoryFlag.objects.get(pk=11)
        self.rig_slot_1 = InventoryFlag.objects.get(pk=92)
        self.drone_bay = InventoryFlag.objects.get(pk=87)
        self.ship_hangar = InventoryFlag.objects.get(pk=90)
        self.fuel_bay = InventoryFlag.objects.get(pk=133)

    def test_nice_name(self):
        # Test name lookups
        self.assertEqual(self.hi_slot_1.nice_name(), 'High Slot')
        self.assertEqual(self.med_slot_1.nice_name(), 'Mid Slot')
        self.assertEqual(self.low_slot_1.nice_name(), 'Low Slot')
        self.assertEqual(self.rig_slot_1.nice_name(), 'Rig Slot')
        self.assertEqual(self.drone_bay.nice_name(), 'Drone Bay')
        self.assertEqual(self.ship_hangar.nice_name(), 'Ship Hangar')
        self.assertEqual(self.fuel_bay.nice_name(), 'Fuel Bay')

    def test_sort_order(self):
        # Test sort order lookups
        flags = [self.fuel_bay, self.ship_hangar, self.drone_bay, self.rig_slot_1,
                 self.low_slot_1, self.med_slot_1, self.hi_slot_1]
        flags.sort(key=lambda f: f.sort_order())

        self.assertEqual(flags, [self.hi_slot_1, self.med_slot_1, self.low_slot_1, self.rig_slot_1,
                                 self.drone_bay, self.ship_hangar, self.fuel_bay])


class BlueprintTestCase(TestCase):
    fixtures = ['blueprint_testdata.json']

    def setUp(self):
        super(BlueprintTestCase, self).setUp()

        self.maelstrom_neg4_neg4 = BlueprintInstance.objects.create(
            blueprint_id=24695,
            original=True,
            material_level=-4,
            productivity_level=-4,
        )

        self.maelstrom_0_0 = BlueprintInstance.objects.create(
            blueprint_id=24695,
            original=True,
            material_level=0,
            productivity_level=0,
        )

        self.maelstrom_50_10 = BlueprintInstance.objects.create(
            blueprint_id=24695,
            original=True,
            material_level=50,
            productivity_level=10,
        )

        self.comps_neg4_neg4 = self.maelstrom_neg4_neg4._get_components()
        self.comps_0_0 = self.maelstrom_0_0._get_components()
        self.comps_50_10 = self.maelstrom_50_10._get_components()

    def test_calc_production_time(self):
        self.assertEqual(self.maelstrom_neg4_neg4.calc_production_time(), 28800)
        self.assertEqual(self.maelstrom_0_0.calc_production_time(), 14400)
        self.assertEqual(self.maelstrom_50_10.calc_production_time(), 11782)

    def test_calc_production_cost(self):
        # Production cost from buys
        self.assertEqual(self.maelstrom_neg4_neg4.calc_production_cost(), Decimal('319598442.95'))
        self.assertEqual(self.maelstrom_0_0.calc_production_cost(), Decimal('234372093.37'))
        self.assertEqual(self.maelstrom_50_10.calc_production_cost(), Decimal('213480621.36'))

        # Production cost from sells
        self.assertEqual(self.maelstrom_neg4_neg4.calc_production_cost(use_sell=True), Decimal('324144004.04'))
        self.assertEqual(self.maelstrom_0_0.calc_production_cost(use_sell=True), Decimal('237705504.90'))
        self.assertEqual(self.maelstrom_50_10.calc_production_cost(use_sell=True), Decimal('216516866.94'))

    def test_get_components(self):
        comps = [(item.name, n) for item, n in self.comps_neg4_neg4]
        comps.sort(key=lambda c: c[1])
        self.assertEqual(comps, [('Megacyte', 3413), ('Zydrine', 14801), ('Nocxium', 62129), ('Isogen', 248777),
                                 ('Mexallon', 995930),
                                 ('Pyerite', 3982146), ('Tritanium', 15926640)])

        comps = [(item.name, n) for item, n in self.comps_0_0]
        comps.sort(key=lambda c: c[1])
        self.assertEqual(comps, [('Megacyte', 2503), ('Zydrine', 10854), ('Nocxium', 45561), ('Isogen', 182436),
                                 ('Mexallon', 730348),
                                 ('Pyerite', 2920240), ('Tritanium', 11679536)])

        comps = [(item.name, n) for item, n in self.comps_50_10]
        comps.sort(key=lambda c: c[1])
        self.assertEqual(comps, [('Megacyte', 2279), ('Zydrine', 9886), ('Nocxium', 41500), ('Isogen', 166176),
                                 ('Mexallon', 665255),
                                 ('Pyerite', 2659969), ('Tritanium', 10638579)])
