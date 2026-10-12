def odgovara(broj, min_cena, max_cena):
    if broj is None:
        return False

    if min_cena is not None and broj < min_cena:
        return False

    if max_cena is not None and broj > max_cena:
        return False

    # if not min:
    #     min_cena is not None
    #     return False

    return True


print(odgovara(54000, 25000, 60000))
print(odgovara(72000, 25000, 60000))
print(odgovara(54000, None, 60000))
print(odgovara(10000, None, 60000))
print(odgovara(90000, 25000, None))
print(odgovara(54000, None, None))
print(odgovara(None, 25000, 60000))
