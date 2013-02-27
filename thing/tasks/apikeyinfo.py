from .apitask import APITask

from thing.models import APIKey, Character, CharacterConfig, CharacterDetails, Corporation

# ---------------------------------------------------------------------------

class APIKeyInfo(APITask):
    name = 'thing.api_key_info'

    def run(self, url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        if self.fetch_api(url, {}) is False or self.root is None:
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

        # Gather data
        characters = {}
        corporations = {}
        for row in key_node.findall('rowset/row'):
            characters[int(row.attrib['characterID'])] = (row.attrib['characterName'], int(row.attrib['corporationID']))
            corporations[int(row.attrib['corporationID'])] = row.attrib['corporationName']

        # Bulk query data
        char_map = Character.objects.select_related('config', 'corporation', 'details').in_bulk(characters.keys())
        corp_map = Corporation.objects.in_bulk(corporations.keys())

        # Create any new Corporation objects
        new_corps = []
        for corp_id, corp_name in corporations.items():
            if corp_id not in corp_map:
                new_corps.append(Corporation(
                    id=corp_id,
                    name=corp_name,
                ))

        Corporation.objects.bulk_create(new_corps)

        # Create any new Character objects
        new_chars = []
        new_configs = []
        new_details = []
        for char_id, (char_name, corp_id) in characters.items():
            if char_id not in char_map:
                new_chars.append(Character(
                    id=char_id,
                    name=char_name,
                    corporation_id=corp_id,
                ))
                new_configs.append(CharacterConfig(character_id=char_id))
                new_details.append(CharacterDetails(character_id=char_id))

        # Fix any existing Character objects with missing Config/Details
        for char_id, char in char_map.items():
            if char.config is None:
                new_configs.append(CharacterConfig(character_id=char_id))
            if char.details is None:
                new_details.append(CharacterDetails(character_id=char_id))

            # Handle name/corporation changes
            if char.name != characters[char.id][0] or char.corporation_id != characters[char.id][1]:
                char.name = characters[char.id][0]
                char.corporation_id = characters[char.id][1]
                char.save()

        Character.objects.bulk_create(new_chars)
        CharacterConfig.objects.bulk_create(new_configs)
        CharacterDetails.objects.bulk_create(new_details)


        # Account/Character key
        if self.apikey.key_type in (APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE):
            self.apikey.corp_character = None

        # Corporation key
        elif self.apikey.key_type == APIKey.CORPORATION_TYPE:
            self.apikey.corp_character_id = characters.keys()[0]

        # Save any APIKey changes
        self.apikey.save()

        # Iterate over all APIKeys with this (keyid, vcode) combo
        for ak in APIKey.objects.filter(keyid=self.apikey.keyid, vcode=self.apikey.vcode):
            # Add characters to this APIKey
            ak.characters.add(*characters.keys())

            # Remove any missing characters from the APIKey
            for char in ak.characters.all():
                if char.id not in characters:
                    ak.characters.remove(char)

        return True

# ---------------------------------------------------------------------------
