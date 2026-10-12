from bs4 import BeautifulSoup
from scraper import parse_price

def odgovara (broj, min_cena, max_cena): 
    if broj is not None and broj < max_cena and broj > min_cena:
        return True
    return False

html = """
<div class="oglas"><a class="SearchAdTitle">Стан во центар</a><span class="cena">54.000 €</span></div>
<div class="oglas"><a class="SearchAdTitle">Гарсоњера Нова Битола</a></div>
<div class="oglas"><a class="SearchAdTitle">Трособен стан</a><span class="cena">72.000 €</span></div>
<div class="oglas"><a class="SearchAdTitle">Мал стан Боулевар</a><span class="cena">21.000 €</span></div>
"""

soup = BeautifulSoup(html, "html.parser")
oglasi = soup.select(".oglas")

rezultati = []

for oglas in oglasi:
    naslov = oglas.select_one(".SearchAdTitle").get_text()

    cena_el = oglas.select_one(".cena")
    if cena_el:
        cena = cena_el.get_text()
    else:
        cena = "По договор"

    broj, valuta = parse_price(cena)

    rezultati.append({
        "naslov": naslov,
        "cena": cena,
        "broj": broj,
    })

for r in rezultati:
    print(r)

print("--- Од 25.000 до 60.000 € ---")

for r in rezultati:
    if  odgovara(r["broj"], 25000, 60000):
        print(r)