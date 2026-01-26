import random


def main():
    numbers = [
        {1: "uno"},
        {2: "dos"},
        {3: "tres"},
        {4: "cuatro"},
        {5: "cinco"},
        {6: "seis"},
        {7: "siete"},
        {8: "ocho"},
        {9: "nueve"},
        {10: "diez"},
        {11: "once"},
        {12: "doce"},
        {13: "trece"},
        {14: "catorce"},
        {15: "quince"},
        {16: "dieciséis"},
        {17: "diecisiete"},
        {18: "dieciocho"},
        {19: "diecinueve"},
        {20: "veinte"},
        {21: "veintiuno"},
        {22: "veintidós"},
        {23: "veintitrés"},
        {24: "veinticuatro"},
        {25: "veinticinco"},
        {26: "veintiséis"},
        {27: "veintisiete"},
        {28: "veintiocho"},
        {29: "veintinueve"},
        {30: "treinta"},
        {31: "treintayuno"},
        {32: "treintaydos"},
        {33: "treintaytres"},
        {40: "cuarenta"},
        {41: "cuarentayuno"},
        {42: "cuarentaydos"},
        {50: "cincuenta"},
        {60: "sesenta"},
        {70: "setenta"},
        {80: "ochenta"},
        {90: "noventa"},
        {100: "cien"},
        {101: "cientouno"},
        {102: "cientodos"},
        {110: "cientodiez"},
        {111: "cientoonce"},
        {200: "doscientos"},
        {201: "doscientosuno"},
        {202: "doscientosdos"},
        {211: "doscientosonce"},
        {276: "doscientossetentayseis"},
        {300: "trescientos"},
        {400: "cuatrocientos"},
        {500: "quinientos"},
        {600: "seiscientos"},
        {700: "setecientos"},
        {800: "ochocientos"},
        {900: "novecientos"},
        {1000: "mil"},
        {1011: "milonce"},
        {1111: "milcientoonce"},
        {2000: "dosmil"},
        {3000003: "tres millones tres"},
    ]

    sample = random.choice(numbers)
    digits = list(sample.keys())[0]
    print(digits)
    words = sample[digits]
    print(words)

if __name__ == "__main__":
    main()
