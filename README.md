# NPC GENERATOR

## SUMMARY
I wanted an NPC creator, but everytime I ran them I was disappointed with names, location, etc for any tool I used. This module started with world_connections.json where a location is chosen. For example, the dwarven town of Togdha:

`    "Togdha": {
        "pantheon_weights": { "Dwarven Gods": 10 },
        "organization_weights": { "Miners Guild": 5, "Smiths Guild": 4, "Clan Watch": 3 },
        "race_weights": { "Dwarf": 10, "Human": 1 },
        "name_style": "dwarven_norse"
    },`

Inside are the details about that locale, their gods, names, organizations etc. Note the numbers indicate the prevelance of any entries. From there I have the relevant json files to support the hometowns, organizations, etc. What brings it all together is Ollama phi3, a locally run AI that digs through the json files and comes up with a suitable.  Finally, we create a set of FoundryVTT importable json file formatted for v13 DnD5e and DaggerHeart. 

Because FoundryVTT now has an import ability the process it simply a matter of creating a fake actor, then right-clicking and importing the .json.

    


## USAGE
Kanka.io offers backups of any content you create there and that's my data source.
I exported the data from kanka.io and then created data maps in the json directory
and finally direct the output into a couple of formats. One for DnD5e and the other
for DaggerHeart on FoundryVTT.

## TODO
* Images - I'd love to integrate some image for these NPC.
* Kanka.io - Import.  I wrote the code for the ability to create a character from this directly into Kanka, but I haven't tested it. I bet it works, but first you'll need a kanka_id_map.json and of course API access.
