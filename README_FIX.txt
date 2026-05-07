Oppdatert versjon – pris- og lenkefiks

Endret:
- utils.py: Tall uten prismerking tolkes ikke lenger som pris. BMV-712 blir derfor ikke 712 kr.
- scraper.py: Leser produktpriser fra strukturerte JSON/script-data når pris ikke ligger i vanlig HTML.
- Salgspris/final_price prioriteres foran førpris/regular_price der begge finnes.
- scraper.py: Gamle lagrede produkter med døde lenker blir ikke lenger beholdt etter oppdatering.
- scraper.py: Hvis Makspower har flyttet et produkt til ny URL, fjernes den gamle duplikatraden slik at «Åpne» peker til den nye fungerende produktsiden.

Test:
- Python-filene kompilerer uten syntaksfeil.
- Bekreftet at den døde Makspower-lenken /produkt/orion-tr-smart-dc-dc-lader-isolert returnerer 404.
- Bekreftet at riktig Makspower-lenke for 12/12-30A er /produkt/victron-orion-tr-smart-12-12-30a-isolert-dc-dc-lader.

Start:
1. Pakk ut zip-en.
2. Dobbeltklikk start_all.bat.
3. Åpne/bruk dashboardet og trykk «Oppdater nå». Hvis siden allerede var åpen, stopp vinduet og start på nytt først.

Merk:
Denne zip-en inneholder alle filene jeg mottok, med scraper.py og utils.py oppdatert.
