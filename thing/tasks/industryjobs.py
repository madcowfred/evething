import datetime

from .apitask import APITask

from thing.models import Character, IndustryJob, Event, InventoryFlag, Item, System

# ---------------------------------------------------------------------------

class IndustryJobs(APITask):
    name = 'thing.industry_jobs'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return
        
        # Make sure the character exists
        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return

        # Initialise for corporate key
        if self.apikey.corp_character:
            ij_filter = IndustryJob.objects.filter(corporation=character.corporation)
        # Initialise for other keys
        else:
            ij_filter = IndustryJob.objects.filter(corporation=None, character=character)

        # Fetch the API data
        params = { 'characterID': character_id }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        # Generate a job id map
        job_map = {}
        for ij in ij_filter:
            job_map[ij.job_id] = ij
        
        # Iterate over the returned result set
        now = datetime.datetime.now()
        flag_ids = set()
        item_ids = set()
        system_ids = set()

        rows = []
        for row in self.root.findall('result/rowset/row'):
            job_id = int(row.attrib['jobID'])
            
            # Job exists
            ij = job_map.get(job_id, None)
            if ij is not None:
                # Job is still active, update relevant details
                if row.attrib['completed'] == '0':
                    install_time = self.parse_api_date(row.attrib['installTime'])
                    begin_time = self.parse_api_date(row.attrib['beginProductionTime'])
                    end_time = self.parse_api_date(row.attrib['endProductionTime'])
                    pause_time = self.parse_api_date(row.attrib['pauseProductionTime'])

                    if install_time > ij.install_time or begin_time > ij.begin_time or end_time > ij.end_time or \
                       pause_time > ij.pause_time:
                        ij.install_time = install_time
                        ij.begin_time = begin_time
                        ij.end_time = end_time
                        ij.pause_time = pause_time
                        ij.save()

                # Job is now complete, issue an event
                elif row.attrib['completed'] and not ij.completed:
                    ij.completed = True
                    ij.completed_status = row.attrib['completedStatus']
                    ij.save()

                    text = 'Industry Job #%s (%s, %s) has been delivered' % (ij.job_id, ij.system.name, ij.get_activity_display())
                    event = Event(
                        user_id=self.apikey.user.id,
                        issued=now,
                        text=text,
                    )
                    event.save()

            # Doesn't exist, save data for later
            else:
                flag_ids.add(int(row.attrib['installedItemFlag']))
                flag_ids.add(int(row.attrib['outputFlag']))
                item_ids.add(int(row.attrib['installedItemTypeID']))
                item_ids.add(int(row.attrib['outputTypeID']))
                system_ids.add(int(row.attrib['installedInSolarSystemID']))

                rows.append(row)

        # Bulk query data
        flag_map = InventoryFlag.objects.in_bulk(flag_ids)
        item_map = Item.objects.in_bulk(item_ids)
        system_map = System.objects.in_bulk(system_ids)

        # Create new IndustryJob objects
        new = []
        for row in rows:
            installed_item = item_map.get(int(row.attrib['installedItemTypeID']))
            if installed_item is None:
                logger.warn("industry_jobs: No matching Item %s", row.attrib['installedItemTypeID'])
                continue

            installed_flag = flag_map.get(int(row.attrib['installedItemFlag']))
            if installed_flag is None:
                logger.warn("industry_jobs: No matching InventoryFlag %s", row.attrib['installedItemFlag'])
                continue

            output_item = item_map.get(int(row.attrib['outputTypeID']))
            if output_item is None:
                logger.warn("industry_jobs: No matching Item %s", row.attrib['outputTypeID'])
                continue

            output_flag = flag_map.get(int(row.attrib['outputFlag']))
            if output_flag is None:
                logger.warn("industry_jobs: No matching InventoryFlag %s", row.attrib['outputFlag'])
                continue

            system = system_map.get(int(row.attrib['installedInSolarSystemID']))
            if system is None:
                logger.warn("industry_jobs: No matching System %s", row.attrib['installedInSolarSystemID'])
                continue

            # Create the new job object
            ij = IndustryJob(
                character=character,
                job_id=row.attrib['jobID'],
                assembly_line_id=row.attrib['assemblyLineID'],
                container_id=row.attrib['containerID'],
                location_id=row.attrib['installedItemLocationID'],
                item_productivity_level=row.attrib['installedItemProductivityLevel'],
                item_material_level=row.attrib['installedItemMaterialLevel'],
                licensed_production_runs_remaining=row.attrib['installedItemLicensedProductionRunsRemaining'],
                output_location_id=row.attrib['outputLocationID'],
                installer_id=row.attrib['installerID'],
                runs=row.attrib['runs'],
                licensed_production_runs=row.attrib['licensedProductionRuns'],
                system=system,
                container_location_id=row.attrib['containerLocationID'],
                material_multiplier=row.attrib['materialMultiplier'],
                character_material_multiplier=row.attrib['charMaterialMultiplier'],
                time_multiplier=row.attrib['timeMultiplier'],
                character_time_multiplier=row.attrib['charTimeMultiplier'],
                installed_item=installed_item,
                installed_flag=installed_flag,
                output_item=output_item,
                output_flag=output_flag,
                completed=row.attrib['completed'],
                completed_status=row.attrib['completedStatus'],
                activity=row.attrib['activityID'],
                install_time=self.parse_api_date(row.attrib['installTime']),
                begin_time=self.parse_api_date(row.attrib['beginProductionTime']),
                end_time=self.parse_api_date(row.attrib['endProductionTime']),
                pause_time=self.parse_api_date(row.attrib['pauseProductionTime']),
            )
            
            if self.apikey.corp_character:
                ij.corporation = self.apikey.corp_character.corporation

            new.append(ij)

        # Insert any new orders
        if new:
            IndustryJob.objects.bulk_create(new)

        return True

# ---------------------------------------------------------------------------
