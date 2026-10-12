import re
import requests
from scraper import HEADERS, BASE_URL

def zemi_datum(ad_id):
    url = BASE_URL + "/AdDetails?ad=" + str(ad_id)
    html = requests.get(url, headers=HEADERS, timeout=30).text

    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", html)
    if not m:
        return None

    den, mesec, godina = m.group(1), m.group(2), m.group(3)
    return godina + "-" + mesec + "-" + den

print(zemi_datum(5841954))
print(zemi_datum(5828001))
