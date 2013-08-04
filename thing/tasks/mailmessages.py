from .apitask import APITask

from thing.models.apikey import APIKey
from thing.models.character import Character
from thing.models.mailmessage import MailMessage

# ---------------------------------------------------------------------------

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
        params = { 'characterID': character_id }
        if self.fetch_api(url, params) is False or self.root is None:
            return

        # Collect mail from XML
        char_ids = set()
        mail = {}
        for row in self.root.findall('result/rowset/row'):
            mail[int(row.attrib['messageID'])] = row.attrib

            tci = row.attrib['toCharacterIDs'].split(',')
            if len(tci) == 1 and tci[0] == '':
                continue

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

        # Create any new Character objects
        if new:
            Character.objects.bulk_create(new)

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
            #else:

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
            newurl = url.replace('Messages', 'Bodies')
            params['ids'] = ','.join(map(str, mail.keys()))
            if self.fetch_api(newurl, params) is False or self.root is None:
                return

            # New list of mail IDs
            mail_bodies = {}
            for row in self.root.findall('result/rowset/row'):
                mail_bodies[int(row.attrib['messageID'])] = row.text.replace('<br>', '\n')

            # Bulk fetch mail from database and update any new body fields
            for mm in m_filter.filter(message_id__in=mail_bodies.keys()):
                if mm.body != mail_bodies[mm.message_id]:
                    mm.body = mail_bodies[mm.message_id]
                    mm.save(update_fields=('body',))

        return True

# ---------------------------------------------------------------------------
