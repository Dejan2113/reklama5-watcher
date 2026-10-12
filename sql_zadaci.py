import sqlite3
from pathlib import Path

PAPKA = Path(__file__).parent
conn = sqlite3.connect(PAPKA /"reklama5.db")

print("--Zadaca 1--")

for red in conn.execute("""
    SELECT title, price
    FROM ads
    ORDER BY price
    LIMIT 10
"""):
    print(red)

print("--Zadaca 2--")
broj = conn.execute("SELECT COUNT(*) FROM ads WHERE rooms> 3").fetchone()[0]
print(broj)

print("--Zadaca 3--")
for red in conn.execute("""
    SELECT  title
    From ads
    WHERE title LIKE '%centar%'
    OR title LIKE '%центар%'
    OR title LIKE '%Центар%'
    OR title LIKE '%ЦЕНТАР%'
"""):
    print(red)

broj = conn.execute("""SELECT COUNT(*) FROM ADS WHERE 
    title LIKE '%centar%'
    OR title LIKE '%центар%'
    OR title LIKE '%Центар%'
    OR title LIKE '%ЦЕНТАР%'""").fetchone()[0]

print(broj)

print("--Zadaca 4--")
so_m2 = conn.execute("SELECT COUNT(*), ROUND(AVG(price)) FROM ads WHERE m2 IS NOT NULL").fetchone()[0]
print(so_m2)

bez_m2 = conn.execute("SELECT COUNT(*), ROUND(AVG(price)) FROM ads WHERE m2 IS NULL").fetchone()[0]
print(bez_m2)

print("--Zadaca 5--")
for red in conn.execute(""" 
SELECT city, COUNT(*), ROUND(AVG(m2)) FROM ads GROUP BY city
"""):
    print(red)

print("--Zadaca 6--")
for red in conn.execute("""
SELECT city, COUNT(*), ROUND(AVG(m2)) FROM ads GROUP BY city HAVING AVG(m2) > 50
"""):
    print(red)

print("--Zadaca 7--")
for red in conn.execute("""
SELECT city, COUNT(*) FROM ads WHERE favorite = 1 GROUP BY city
"""):
    print(red)


print("--Zadaca 8--")
for red in conn.execute("""
SELECT city, ROUND(MAX(price / m2)) FROM ads WHERE m2 IS NOT NULL GROUP BY city
"""):
    print(red)

print("--Zadaca 9--")
for red in conn.execute("""
SELECT 
    CASE
        WHEN price IS NULL THEN 'без цена'
        WHEN price < 40000 THEN 'евтин'
        WHEN price <= 50000 THEN 'среден'
        ELSE 'скап'
    END AS kategorija,
    COUNT(*)
FROM ads
GROUP BY kategorija
"""):
    print(red)

print("--Zadaca 10--")
for red in conn.execute("""
SELECT city, ROUND(MAX(price) - MIN(price)) AS razlika FROM ads GROUP BY city ORDER BY razlika LIMIT 1
"""):
    print(red)

print("--Vezba--")
