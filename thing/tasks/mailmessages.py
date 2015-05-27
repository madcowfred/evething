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

from django.db import IntegrityError

from celery.execute import send_task

from .apitask import APITask

from thing.models.apikey import APIKey
from thing.models.character import Character
from thing.models.mailmessage import MailMessage


class MailMessages(APITask):
    name = 'thing.mail_messages'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Set up our queryset
        m_filter = MailMessage.objects.filter(
            character=character_id,
        )

        # Fetch the API data
        params = {'characterID': character_id}
        if self.fetch_api(url, params) is False or self.root is None:
            return

        # Collect mail from XML
        char_ids = set()
        mail = {}
        for row in self.root.findall('result/rowset/row'):
            mail[int(row.attrib['messageID'])] = row.attrib

            char_ids.add(int(row.attrib['senderID']))

            # Add all of toCharacterIDs to our set
            tci = row.attrib['toCharacterIDs'].split(',')
            if len(tci) > 0 and tci[0] != '':
                char_ids.update(map(int, tci))

        # Bulk fetch characters from database
        new = []
        char_map = Character.objects.in_bulk(list(char_ids))
        for char_id in char_ids:
            if char_id not in char_map:
                new.append(Character(
                    id=char_id,
                    name='*UNKNOWN*',
                ))

        # Create any new Character objects one at a time, oh dear
        for character in new:
            try:
                character.save()
            except IntegrityError:
                continue

        # Bulk fetch mail from database
        mail_map = {}
        for mm in m_filter.filter(message_id__in=mail.keys()):
            mail_map[mm.message_id] = mm

        # Add/update mail
        new = []
        for messageID, attrib in mail.items():
            mm = mail_map.get(messageID)

            # MailMessage doesn't exist, create a new one
            if mm is None:
                toCorpOrAllianceID = attrib.get('toCorpOrAllianceID', '') or 0
                toListID = attrib.get('toListID', '') or 0

                new.append(MailMessage(
                    character_id=character_id,
                    message_id=messageID,
                    sender_id=attrib['senderID'],
                    sent_date=self.parse_api_date(attrib['sentDate']),
                    title=attrib['title'],
                    to_corp_or_alliance_id=toCorpOrAllianceID,
                    to_list_id=toListID,
                    body=None,
                ))

            # MailMessage does exist, not caring since mail headers should never change :ccp:
            # else:

        # Create any new MailMessage objects
        if new:
            MailMessage.objects.bulk_create(new)

        # Re-fetch all of those stupid MailMessage objects so we can add characters
        m_filter.update()
        for mm in m_filter.filter(message_id__in=mail.keys()):
            characters = mail[mm.message_id]['toCharacterIDs'].split(',')
            if len(characters) == 1 and characters[0] == '':
                continue

            mm.to_characters.add(*map(int, characters))

        # If this key is able to, fetch MailBodies now
        if mail.keys() and (self.apikey.access_mask & APIKey.CHAR_MAIL_BODIES_MASK == APIKey.CHAR_MAIL_BODIES_MASK):
            ids = ','.join(map(str, mail.keys()))
            send_task(
                'thing.mail_bodies',
                args=(apikey_id, character_id, ids),
                kwargs={},
                queue='et_medium',
            )

        return True
