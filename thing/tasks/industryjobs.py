# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

import datetime

from .apitask import APITask

from thing.models import Character, IndustryJob, Event, Item, Blueprint, System, APIKey


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
        if self.apikey.key_type == APIKey.CORPORATION_TYPE:
            ij_filter = IndustryJob.objects.filter(corporation=character.corporation)
        # Initialise for other keys
        else:
            ij_filter = IndustryJob.objects.filter(corporation__isnull=True, character=character)

        ij_filter = ij_filter.select_related('character', 'corporation')

        # Fetch the API data
        params = {'characterID': character_id}
        if self.fetch_api(url, params) is False or self.root is None:
            self.log_info('API error')
            return

        # Generate a job id map
        job_map = {}
        for ij in ij_filter:
            job_map[ij.job_id] = ij

        # Iterate over the returned result set
        now = datetime.datetime.now()
        item_ids = set()
        blueprint_ids = set()
        system_ids = set()

        rows = []
        new_events = []
        for row in self.root.findall('result/rowset/row'):
            job_id = int(row.attrib['jobID'])

            # Job exists
            ij = job_map.get(job_id, None)
            if ij is not None:
                # Update changable details
                start_date = self.parse_api_date(row.attrib['startDate'])
                end_date = self.parse_api_date(row.attrib['endDate'])
                pause_date = self.parse_api_date(row.attrib['pauseDate'])
                completed_date = self.parse_api_date(row.attrib['completedDate'])
                duration = row.attrib['timeInSeconds']
                status = row.attrib['status']
                product = row.attrib['productTypeID']

                # Only update if stuff changed
                if (start_date != ij.start_date or end_date != ij.end_date or pause_date != ij.pause_date or
                            completed_date != ij.pause_date or status != ij.status or product != ij.product):

                    if row.attrib['productTypeID'] != '0':
                        ij.product_id = product

                    ij.start_date = start_date
                    ij.end_date = end_date
                    ij.pause_date = pause_date
                    ij.completed_date = completed_date
                    ij.duration = duration
                    ij.status = status
                    ij.save()

                    if ij.status != 1:
                        text = '%s: industry job #%s (%s) status has been changed to ' % (ij.system.name, ij.job_id, ij.get_activity_display())
                        if self.apikey.key_type == APIKey.CORPORATION_TYPE:
                            text = '%s ([%s] %s)' % (text, ij.corporation.ticker, ij.corporation.name)
                        else:
                            text = '%s (%s)' % (text, ij.character.name)

                        new_events.append(Event(
                            user_id=self.apikey.user.id,
                            issued=now,
                            text=text,
                        ))
            # Doesn't exist, save data for later
            else:
                blueprint_ids.add(int(row.attrib['blueprintTypeID']))
                item_ids.add(int(row.attrib['productTypeID']))
                system_ids.add(int(row.attrib['solarSystemID']))

                rows.append(row)

        # Create any new events
        Event.objects.bulk_create(new_events)

        # Bulk query data
        item_map = Item.objects.in_bulk(item_ids)
        blueprint_map = Blueprint.objects.in_bulk(blueprint_ids)
        system_map = System.objects.in_bulk(system_ids)

        # Create new IndustryJob objects
        new = []
        seen_jobs = []
        for row in rows:
            jobID = int(row.attrib['jobID'])
            seen_jobs.append(jobID)

            blueprint = blueprint_map.get(int(row.attrib['blueprintTypeID']))
            if blueprint is None:
                self.log_warn("industry_jobs: No matching blueprint Item %s", row.attrib['blueprintTypeID'])
                continue

            product = item_map.get(int(row.attrib['productTypeID']))
            if product is None:
                self.log_warn("industry_jobs: No matching product Item %s", row.attrib['productTypeID'])
                # this apparently is normal to be set to 0, woo :ccp:

            system = system_map.get(int(row.attrib['solarSystemID']))
            if system is None:
                self.log_warn("industry_jobs: No matching System %s", row.attrib['solarSystemID'])
                continue

            # Create the new job object
            ij = IndustryJob(
                character=character,
                job_id=jobID,
                installer_id=row.attrib['installerID'],
                system=system,
                activity=row.attrib['activityID'],
                blueprint=blueprint,
                output_location_id=row.attrib['outputLocationID'],
                runs=row.attrib['runs'],
                team_id=row.attrib['teamID'],
                licensed_runs=row.attrib['licensedRuns'],
                product=product,
                status=row.attrib['status'],
                duration=row.attrib['timeInSeconds'],
                start_date=self.parse_api_date(row.attrib['startDate']),
                end_date=self.parse_api_date(row.attrib['endDate']),
                pause_date=self.parse_api_date(row.attrib['pauseDate']),
                completed_date=self.parse_api_date(row.attrib['completedDate'])
            )

            if self.apikey.key_type == APIKey.CORPORATION_TYPE:
                ij.corporation = self.apikey.corporation

            new.append(ij)

        # Insert any new jobs
        if new:
            IndustryJob.objects.bulk_create(new)

        # Clean up old jobs in weird states
        unknowns = ij_filter.filter(
            status=1,
            end_date__lte=datetime.datetime.utcnow() - datetime.timedelta(days=90),
        ).exclude(
            job_id__in=seen_jobs,
        ).update(
            status=IndustryJob.UNKNOWN_STATUS
        )
        if unknowns > 0:
            self.log_warn('%d jobs set to UNKNOWN state.' % unknowns)

        return True
