try:
    import xml.etree.cElementTree as ET
except:
    import xml.etree.ElementTree as ET

from thing.models import *


def parse_emp_plan(skillplan, data):
    root = ET.fromstring(data)

    position = 0
    for entry in root.findall('entry'):
        #print entry
        # Create the various objects for the remapping if it exists
        remapping = entry.find('remapping')
        if remapping:
            # <remapping status="UpToDate" per="17" int="27" mem="21" wil="17" cha="17" description="" />
            spr = SPRemap.objects.create(
                int_stat=remapping.attrib['int'],
                mem_stat=remapping.attrib['mem'],
                per_stat=remapping.attrib['per'],
                wil_stat=remapping.attrib['wil'],
                cha_stat=remapping.attrib['cha'],
            )

            spe = SPEntry.objects.create(
                skill_plan=skillplan,
                position=position,
                sp_remap=spr,
            )

            position += 1

        # Create the various objects for the skill
        sps = SPSkill.objects.create(
            skill_id=entry.attrib['skillID'],
            level=entry.attrib['level'],
            priority=entry.attrib['priority'],
        )
        spe = SPEntry.objects.create(
            skill_plan=skillplan,
            position=position,
            sp_skill=sps,
        )

        position += 1
