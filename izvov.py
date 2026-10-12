import sqlite3
from pathlib import Path
from openpyxl import Workbook

PAPKA = Path(__file__).parent
conn = sqlite3.connect(PAPKA / "reklama5.db")

kursor = conn.execute("""
    SELECT a.city AS grad, a.title AS naslov, a.price AS cena,
           a.m2, a.rooms AS sobi, a.url AS link
    FROM ads a
    JOIN searches s ON s.id = a.search_id
""")

wb = Workbook()
ws = wb.active
ws.title = "oglasi"

# прв ред: имиња на колоните
ws.append([kolona[0] for kolona in kursor.description])

# потоа сите огласи, еден по еден
broj = 0
for red in kursor:
    ws.append(list(red))
    broj += 1

wb.save(PAPKA / "oglasi.xlsx")
print("Излезни огласи:", broj)

conn.close()