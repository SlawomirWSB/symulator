import streamlit as st
import ccxt
import time
import threading
from datetime import datetime

# =====================================================================
# INTERFEJS GRAFICZNY STREAMLIT
# =====================================================================
st.set_page_config(page_title="🤖 Autonomiczny Bot SPOT", layout="wide")

st.title("🤖 Autonomiczny Multi-Skaner & Bot SPOT (Symulator)")
st.caption("Bot skanuje rynek 24/7 na żywo z Binance. Działa wyłącznie w trendzie wzrostowym (SPOT Long).")

# Inicjalizacja zmiennych w pamięci Streamlita (session_state)
if 'wirtualne_usdt' not in st.session_state:
    st.session_state.wirtualne_usdt = 100.0
if 'historia_zagrań' not in st.session_state:
    st.session_state.historia_zagrań = []
if 'aktywna_pozycja' not in st.session_state:
    st.session_state.aktywna_pozycja = None
if 'status_bota' not in st.session_state:
    st.session_state.status_bota = "Wyłączony"
if 'logi' not in st.session_state:
    st.session_state.logi = []
if 'aktualny_skan' not in st.session_state:
    st.session_state.aktualny_skan = {}

# Funkcja pomocnicza do dodawania logów systemowych
def dodaj_log(tekst):
    teraz = datetime.now().strftime("%H:%M:%S")
    st.session_state.logi.append(f"[{teraz}] {tekst}")
    if len(st.session_state.logi) > 20: # Trzymamy tylko 20 ostatnich linijek logów
        st.session_state.logi.pop(0)

# Matematyczna funkcja RSI (taka sama jak w Twoim skanerze lokalnym)
def oblicz_rsi(ceny_zamkniecia, okres=14):
    if len(ceny_zamkniecia) < okres:
        return 50
    wzrosty, spadki = [], []
    for i in range(1, len(ceny_zamkniecia)):
        roznica = ceny_zamkniecia[i] - ceny_zamkniecia[i-1]
        if roznica > 0:
            wzrosty.append(roznica)
            spadki.append(0)
        else:
            wzrosty.append(0)
            spadki.append(abs(roznica))
    sredni_wzrost = sum(wzrosty[-okres:]) / okres
    sredni_spadek = sum(spadki[-okres:]) / okres
    if sredni_spadek == 0:
        return 100
    rs = sredni_wzrost / sredni_spadek
    return 100 - (100 / (1 + rs))

# =====================================================================
# SILNIK BOTA (DZIAŁAJĄCY W TLE SERWERA)
# =====================================================================
def silnik_bota_w_tle():
    gielda = ccxt.binance()
    WATCHLISTA = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
    INTERWAL = "5m"
    wielkosc_pozycji_usd = 25.0 # Wirtualna stawka na jeden trade

    while st.session_state.status_bota == "Uruchomiony":
        try:
            # PRZYPADEK 1: SZUKAMY PROFILAKTYCZNIE SYGNAŁU KUPNA (BRAK POZYCJI)
            if st.session_state.aktywna_pozycja is None:
                for symbol in WATCHLISTA:
                    # Sprawdzamy bezpiecznik w locie, czy użytkownik nie kliknął stop
                    if st.session_state.status_bota != "Uruchomiony": break
                    
                    swiece = gielda.fetch_ohlcv(symbol, timeframe=INTERWAL, limit=50)
                    ceny_zamkniecia = [swieca[4] for swieca in swiece]
                    aktualna_cena = ceny_zamkniecia[-1]
                    rsi = oblicz_rsi(ceny_zamkniecia)
                    
                    # Aktualizujemy panel skanera na żywo dla użytkownika
                    st.session_state.aktualny_skan[symbol] = {"cena": aktualna_cena, "rsi": rsi}
                    
                    # Warunek czystego SPOT (RSI < 35 oznacza głębokie wyprzedanie)
                    if rsi < 35:
                        cena_tp = aktualna_cena * 1.004 # Target: +0.4% zysku
                        cena_sl = aktualna_cena * 0.996 # Obrona: -0.4% straty
                        ilosc_monet = wielkosc_pozycji_usd / aktualna_cena
                        
                        st.session_state.aktywna_pozycja = {
                            'symbol': symbol, 'wejscie': aktualna_cena,
                            'tp': cena_tp, 'sl': cena_sl, 'ilosc': ilosc_monet
                        }
                        dodaj_log(f"🚨 [SYGNAŁ] Kupiłem wirtualnie {symbol} po {aktualna_cena} (RSI: {round(rsi, 1)})")
                        break
                    
                    time.sleep(1) # Odstęp, żeby serwer Streamlita nie dostał bana za spam od Binance

            # PRZYPADEK 2: POZYCJA JEST OTWARTA -> PILNUJEMY JEJ CENY
            else:
                pos = st.session_state.aktywna_pozycja
                ticker = gielda.fetch_ticker(pos['symbol'])
                obecna_cena = ticker['last']
                
                # Zdarzenie: TAKE PROFIT
                if obecna_cena >= pos['tp']:
                    zysk = (pos['tp'] - pos['wejscie']) * pos['ilosc']
                    st.session_state.wirtualne_usdt += zysk
                    st.session_state.historia_zagrań.append({
                        "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Moneta": pos['symbol'], "Typ": "TAKE PROFIT",
                        "Wejście": round(pos['wejscie'], 4), "Wyjście": round(obecna_cena, 4),
                        "Wynik USD": f"+{round(zysk, 2)}"
                    })
                    dodaj_log(f"🎉 [TAKE PROFIT] Pozycja na {pos['symbol']} zamknięta z zyskiem!")
                    st.session_state.aktywna_pozycja = None
                    time.sleep(5)

                # Zdarzenie: STOP LOSS
                elif obecna_cena <= pos['sl']:
                    strata = (pos['wejscie'] - pos['sl']) * pos['ilosc']
                    st.session_state.wirtualne_usdt -= strata
                    st.session_state.historia_zagrań.append({
                        "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Moneta": pos['symbol'], "Typ": "STOP LOSS",
                        "Wejście": round(pos['wejscie'], 4), "Wyjście": round(obecna_cena, 4),
                        "Wynik USD": f"-{round(strata, 2)}"
                    })
                    dodaj_log(f"❌ [STOP LOSS] Rynek uderzył w obronę na {pos['symbol']}.")
                    st.session_state.aktywna_pozycja = None
                    time.sleep(5)

            time.sleep(3) # Czas uśpienia głównej pętli bota
        except Exception as e:
            time.sleep(5)

# =====================================================================
# WIZUALIZACJA W PANELU INTERFEJSU
# =====================================================================

# BOCZNY PANEL STEROWANIA (Sidebar)
with st.sidebar:
    st.header("⚙️ Zarządzanie Systemem")
    if st.button("▶️ URUCHOM BOTA W CHMURZE", use_container_width=True):
        if st.session_state.status_bota != "Uruchomiony":
            st.session_state.status_bota = "Uruchomiony"
            # ODPALENIE WĄTKU W TLE
            t = threading.Thread(target=silnik_bota_w_tle)
            t.daemon = True # Wątek umrze automatycznie, jeśli zamkniesz Streamlita
            t.start()
            dodaj_log("System wystartował. Rozpoczynam automatyczne skanowanie...")
            st.rerun()

    if st.button("🛑 ZATRZYMAJ BOTA", use_container_width=True):
        st.session_state.status_bota = "Wyłączony"
        st.session_state.aktualny_skan = {}
        dodaj_log("Wydano rozkaz zatrzymania bota.")
        st.rerun()
        
    st.write("---")
    st.write(f"**Status Silnika:** `{st.session_state.status_bota}`")
    st.metric(label="Wirtualny Portfel SPOT", value=f"{round(st.session_state.wirtualne_usdt, 2)} USDT")

# PANEL GŁÓWNY (Górne podsumowanie)
kol1, kol2 = st.columns(2)

with kol1:
    st.subheader("📡 Radar Skanera (Wykresy 5m)")
    if len(st.session_state.aktualny_skan) == 0:
        st.info("Bot jest wyłączony. Uruchom go w panelu bocznym, aby uruchomić radar.")
    else:
        # Prezentacja wyników radaru w czytelnej tabeli Streamlit
        st.json(st.session_state.aktualny_skan)

with kol2:
    st.subheader("📈 Stan Otwartej Transakcji")
    pos = st.session_state.aktywna_pozycja
    if pos is None:
        st.write("🔒 *Brak otwartych pozycji. Twój kapitał bezpiecznie czeka w USDT.*")
    else:
        st.warning(f"🎰 **Pozycja na monety: {pos['symbol']}**")
        st.write(f"• Cena zakupu: `{round(pos['wejscie'], 4)} USD`")
        st.write(f"• Cel (Take Profit): `{round(pos['tp'], 4)} USD`")
        st.write(f"• Obrona (Stop Loss): `{round(pos['sl'], 4)} USD`")

st.write("---")

# DOLNY PANEL (Logi i Historia)
kol_logi, kol_historia = st.columns([1, 2])

with kol_logi:
    st.subheader("📋 Konsola Logów Systemu")
    if not st.session_state.logi:
        st.write("*Brak logów. Uruchom bota...*")
    else:
        for log in reversed(st.session_state.logi):
            st.code(log, language="text")

with kol_historia:
    st.subheader("📝 Dziennik Zamkniętych Transakcji")
    if not st.session_state.historia_zagrań:
        st.write("*Nie zamknięto jeszcze żadnej transakcji w tej sesji.*")
    else:
        st.dataframe(st.session_state.historia_zagrań, use_container_width=True)

# Przycisk wymuszający ręczne odświeżenie interfejsu strony
if st.session_state.status_bota == "Uruchomiony":
    time.sleep(2)
    st.rerun()