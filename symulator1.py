import streamlit as st
import ccxt
import time
import pandas as pd
from datetime import datetime

# =====================================================================
# KONFIGURACJA STRONY
# =====================================================================
st.set_page_config(page_title="Autonomiczny Bot SPOT", layout="wide", page_icon="🤖")

st.title("🤖 Dashboard: Autonomiczny Bot SPOT")
st.markdown("---")

# Inicjalizacja pamięci podręcznej
if 'wirtualne_usdt' not in st.session_state: st.session_state.wirtualne_usdt = 100.0
if 'historia_zagran' not in st.session_state: st.session_state.historia_zagran = []
if 'aktywna_pozycja' not in st.session_state: st.session_state.aktywna_pozycja = None
if 'status_bota' not in st.session_state: st.session_state.status_bota = "Wyłączony"
if 'logi' not in st.session_state: st.session_state.logi = ["System gotowy do pracy."]
if 'aktualny_skan' not in st.session_state: st.session_state.aktualny_skan = {}

def dodaj_log(tekst):
    teraz = datetime.now().strftime("%H:%M:%S")
    st.session_state.logi.insert(0, f"[{teraz}] {tekst}") 
    if len(st.session_state.logi) > 20: st.session_state.logi.pop()

def oblicz_rsi(ceny_zamkniecia, okres=14):
    if len(ceny_zamkniecia) < okres: return 50
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
    if sredni_spadek == 0: return 100
    rs = sredni_wzrost / sredni_spadek
    return 100 - (100 / (1 + rs))

# =====================================================================
# LOGIKA BOTA (Wykonuje JEDEN obrót przy każdym odświeżeniu strony)
# =====================================================================
def skanuj_rynek():
    gielda = ccxt.binance()
    WATCHLISTA = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
    wielkosc_pozycji_usd = 25.0

    try:
        if st.session_state.aktywna_pozycja is None:
            for symbol in WATCHLISTA:
                swiece = gielda.fetch_ohlcv(symbol, timeframe="5m", limit=50)
                ceny = [s[4] for s in swiece]
                cena = ceny[-1]
                rsi = oblicz_rsi(ceny)
                
                st.session_state.aktualny_skan[symbol] = {"cena": cena, "rsi": rsi}
                
                if rsi < 35:
                    cena_tp = cena * 1.004
                    cena_sl = cena * 0.996
                    ilosc = wielkosc_pozycji_usd / cena
                    
                    st.session_state.aktywna_pozycja = {
                        'symbol': symbol, 'wejscie': cena,
                        'tp': cena_tp, 'sl': cena_sl, 'ilosc': ilosc
                    }
                    dodaj_log(f"🚨 [SYGNAŁ] Wykryto okazję na {symbol}. Wirtualny zakup po {cena}.")
                    break # Przerwij pętlę po zakupie

        else:
            pos = st.session_state.aktywna_pozycja
            ticker = gielda.fetch_ticker(pos['symbol'])
            obecna_cena = ticker['last']
            st.session_state.aktualny_skan[pos['symbol']]['cena'] = obecna_cena
            
            if obecna_cena >= pos['tp']:
                zysk = (pos['tp'] - pos['wejscie']) * pos['ilosc']
                st.session_state.wirtualne_usdt += zysk
                st.session_state.historia_zagran.insert(0, {
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Moneta": pos['symbol'], "Typ": "✅ TAKE PROFIT",
                    "Wejście": round(pos['wejscie'], 4), "Wyjście": round(obecna_cena, 4),
                    "Wynik": f"+{round(zysk, 2)} USD"
                })
                dodaj_log(f"🎉 Zakończono {pos['symbol']} z zyskiem: +{round(zysk, 2)} USD")
                st.session_state.aktywna_pozycja = None

            elif obecna_cena <= pos['sl']:
                strata = (pos['wejscie'] - pos['sl']) * pos['ilosc']
                st.session_state.wirtualne_usdt -= strata
                st.session_state.historia_zagran.insert(0, {
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Moneta": pos['symbol'], "Typ": "❌ STOP LOSS",
                    "Wejście": round(pos['wejscie'], 4), "Wyjście": round(obecna_cena, 4),
                    "Wynik": f"-{round(strata, 2)} USD"
                })
                dodaj_log(f"📉 Pozycja {pos['symbol']} zamknięta ze stratą: -{round(strata, 2)} USD")
                st.session_state.aktywna_pozycja = None

    except Exception as e:
        dodaj_log(f"⚠️ Chwilowy błąd sieci: {str(e)}")

# =====================================================================
# INTERFEJS BOCZNY (SIDEBAR)
# =====================================================================
with st.sidebar:
    st.header("⚙️ Panel Sterowania")
    
    if st.button("▶️ URUCHOM BOTA", type="primary", use_container_width=True):
        if st.session_state.status_bota != "Uruchomiony":
            st.session_state.status_bota = "Uruchomiony"
            dodaj_log("Inicjalizacja silnika... Łączenie z Binance.")
            st.rerun()

    if st.button("🛑 ZATRZYMAJ", use_container_width=True):
        st.session_state.status_bota = "Wyłączony"
        dodaj_log("System zatrzymany przez użytkownika.")
        st.rerun()
        
    st.divider()
    status_kolor = "🟢" if st.session_state.status_bota == "Uruchomiony" else "🔴"
    st.markdown(f"**Status:** {status_kolor} {st.session_state.status_bota}")
    st.metric(label="💰 Kapitał (Wirtualny)", value=f"{round(st.session_state.wirtualne_usdt, 2)} USDT")

# =====================================================================
# GŁÓWNY INTERFEJS (DASHBOARD)
# =====================================================================
kol_radar, kol_pozycja = st.columns([1.5, 1])

with kol_radar:
    st.subheader("📡 Radar Rynkowy (Na Żywo)")
    if st.session_state.status_bota == "Uruchomiony" and len(st.session_state.aktualny_skan) == 0:
        st.info("🔄 Pobieranie danych z Binance...")
    elif len(st.session_state.aktualny_skan) == 0:
        st.info("Bot jest wyłączony. Uruchom go w panelu bocznym.")
    else:
        cols = st.columns(4)
        idx = 0
        for symbol, dane in st.session_state.aktualny_skan.items():
            with cols[idx % 4]:
                rsi_val = dane['rsi']
                kolor_delty = "inverse" if rsi_val < 35 else "normal"
                st.metric(
                    label=symbol.replace("/USDT", ""), 
                    value=f"{round(dane['cena'], 2)}", 
                    delta=f"RSI: {round(rsi_val, 1)}",
                    delta_color=kolor_delty
                )
            idx += 1

with kol_pozycja:
    st.subheader("💼 Aktywna Pozycja")
    pos = st.session_state.aktywna_pozycja
    if pos is None:
        st.success("Brak otwartych pozycji. Kapitał bezpieczny.")
    else:
        st.warning(f"**W trakcie: {pos['symbol']}**")
        st.write(f"💵 Wejście: `{round(pos['wejscie'], 4)}`")
        st.write(f"🎯 Target: `{round(pos['tp'], 4)}`")
        st.write(f"🛡️ Stop: `{round(pos['sl'], 4)}`")

st.divider()

kol_logi, kol_historia = st.columns([1, 2])

with kol_logi:
    st.subheader("📝 Dziennik Operacji")
    logi_tekst = "\n".join(st.session_state.logi)
    st.text_area("Ostatnie zdarzenia", value=logi_tekst, height=250, disabled=True, label_visibility="collapsed")

with kol_historia:
    st.subheader("📚 Historia Transakcji")
    if not st.session_state.historia_zagran:
        st.info("Brak zamkniętych transakcji w tej sesji.")
    else:
        df = pd.DataFrame(st.session_state.historia_zagran)
        st.dataframe(df, use_container_width=True, hide_index=True)

# =====================================================================
# PĘTLA NIESKOŃCZONA DLA CHMURY STREAMLIT
# =====================================================================
if st.session_state.status_bota == "Uruchomiony":
    skanuj_rynek()  # Pobiera ceny i przelicza wskaźniki
    time.sleep(3)   # Odpoczywa 3 sekundy
    st.rerun()      # Odświeża stronę od nowa
