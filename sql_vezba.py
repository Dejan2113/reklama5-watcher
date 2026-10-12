import sqlite3
from pathlib import Path

PAPPKA = Path(__file__).parent
conn = sqlite3.connect(PAPPKA / "reklama5.db")

# for red in conn.execute("SELECT id, name FROM searches"):
#     print(red)

# for red in conn.execute("SELECT title, price, m2 FROM ads LIMIT 5"):
#     print(red)

# FILTER = 1
# def analiza(filter_id): 
#     broj = conn.execute("SELECT COUNT(*) FROM ads WHERE search_id = ?", (filter_id,)).fetchone()[0]
#     print("Broj na stanovi: ", broj)

#     prosecna_cena = conn.execute("SELECT ROUND(AVG(price)) FROM ads WHERE search_id = ?", (filter_id,)).fetchone()[0]
#     print("Prosecna_cena e: ", prosecna_cena)

#     najevtin_stan = conn.execute("SELECT MIN(price) FROM ads WHERE search_id = ?", (filter_id,)).fetchone()[0]
#     print("Najevtin stan e ", najevtin_stan)

#     najskap_stan = conn.execute("SELECT MAX(price) FROM ads WHERE search_id =?", (filter_id,)).fetchone()[0]
#     print("Najskap stan e: ", najskap_stan)


# print("BITOLA: ")
# analiza(1)

# print("OHRID: ")
# analiza(2)

# for red in conn.execute("""
#     SELECT a.title, a.price, s.name
#     FROM ads a
#     JOIN searches s ON s.id = a.search_id
#     LIMIT 5
# """):
#     print(red)

# for red in conn.execute("""
#     SELECT s.name, COUNT(*), ROUND(AVG(a.price)), MIN(a.price), MAX(a.price)
#     FROM ads a
#     JOIN searches s ON s.id = a.search_id
#     WHERE m2 IS NOT NULL AND m2 > 0
#     GROUP BY s.name
    
# """):
#     print("Rezultat od join_group: ", red)

for red in conn.execute("""
    SELECT s.name, COUNT(*), ROUND(AVG(a.price))
    FROM ads a
    JOIN searches s on s.id = a.search_id
    WHERE a.m2 < 60
    GROUP BY s.name
    HAVING COUNT(*) > 20
"""):
    print(red)

print("--- Што е зачувано во филтрите ---")
for red in conn.execute("SELECT id, name, include_words, exclude_words FROM searches"):
    print(red)

print("--- Колку огласи со kupuvam има по филтер ---")
for red in conn.execute("""
    SELECT search_id, COUNT(*), SUM(favorite)
    FROM ads
    WHERE LOWER(title) LIKE '%kupuvam%'
    GROUP BY search_id
"""):
    print(red)

conn.close()