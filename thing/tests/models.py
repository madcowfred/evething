from django.test import TestCase
from thing.models import *

class StationTestCase(TestCase):
    #fixtures = ['region_constellation_system_testdata.json']

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
