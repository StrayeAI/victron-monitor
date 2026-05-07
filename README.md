# Victron Monitor REV18

REV18 retter feil produktmatching i REV07.

## Endringer

- Hovedprodukt og tilbehør matches ikke lenger mot hverandre bare fordi navnene ligner.
- `Victron GX Touch 50` skilles fra `Victron GX Touch 50 Wall Mount` / `veggfeste`.
- Victron artikkelnummer fanges bedre fra URL-er og slugs hos konkurrenter.
- Oversikten viser fortsatt bare produkter med gyldig Makspower-pris.
- Makspower-pris hentes fortsatt fra hovedproduktets prisfelt på produktsiden.

## Kontrollpunkter

- `Victron GX Touch 50 Wall Mount` skal ikke ha Sparelys `GX Touch 50` til 2 600 kr som konkurrent.
- `VICTRON GX Touch 50` skal ikke ha Seatronic `veggfeste` til 229 kr som konkurrent.
- `Batterikabel til VICTRON SHUNT M8+M10 SORT 95mm2` skal vise Makspower `269,00 kr`.

## Start

Kjør `start_all.bat` på Windows. Appen åpner `http://127.0.0.1:8765`.
