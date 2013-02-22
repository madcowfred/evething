import os
import sys

from .apitask import APITask

# need to import model definitions from frontend
from thing.models import APIKey, Character, Corporation

# ---------------------------------------------------------------------------

class APIKeyInfo(APITask):
    name = 'thing.api_key_info'

    def run(self, url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        if self.fetch_api(url, {}) is False or self.root is None:
            self.failed()
            return

        # Find the key node
        key_node = self.root.find('result/key')

        # Update access mask
        self.apikey.access_mask = int(key_node.attrib['accessMask'])
        
        # Update expiry date
        expires = key_node.attrib['expires']
        if expires:
            self.apikey.expires = self.parse_api_date(expires)
        else:
            self.apikey.expires = None
        
        # Update key type
        self.apikey.key_type = key_node.attrib['type']


        # Loop over each character
        seen_chars = {}
        for row in key_node.findall('rowset/row'):
            # Get or create a Corporation object
            corporation, created = Corporation.objects.get_or_create(
                pk=row.attrib['corporationID'],
                defaults={
                    'name': row.attrib['corporationName'],
                },
            )

            # Get or create a Character object
            character, created = Character.objects.select_related('config', 'details').get_or_create(
                pk=row.attrib['characterID'],
                defaults={
                    'name': row.attrib['characterName'],
                    'corporation': corporation,
                },
            )

            seen_chars[character.id] = character

            # Account/Character key
            if self.apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
                self.apikey.corporation = None

                # Character was created, create the related models
                if created:
                    cc = CharacterConfig.objects.create(character=character)
                    cd = CharacterDetails.objects.create(character=character)

                # Character already existed, maybe create/update things
                else:
                    if character.config is None:
                        cc = CharacterConfig.objects.create(character=character)
                    if character.details is None:
                        cd = CharacterDetails.objects.create(character=character)

                    # Handle character renames and corporation changes
                    if character.name != row.attrib['characterName'] or character.corporation != corporation:
                        character.name = row.attrib['characterName']
                        character.corporation = corporation
                        character.save()

            # Corporation key
            elif self.apikey.key_type == APIKey.CORPORATION_TYPE:
                self.apikey.corporation = corporation

                self.apikey.corp_character = character

        # Save any APIKey changes
        self.apikey.save()

        # Iterate over all APIKeys with this (keyid, vcode) combo
        for ak in APIKey.objects.filter(keyid=self.apikey.keyid, vcode=self.apikey.vcode):
            # Add characters to this APIKey
            ak.characters.add(*seen_chars.values())

            # Remove any missing characters from the APIKey
            ak.characters.exclude(pk__in=seen_chars.keys()).delete()

        # Job completed
        self.completed()

# ---------------------------------------------------------------------------
