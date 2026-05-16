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

# Inicjalizacja pamięci podręcznej Streamlita
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
# LOGIKA BOTA (Wykonuje JEDEN pełen obieg rynku co 10 sekund)
# =====================================================================
def skanuj_rynek():
    gielda = ccxt.binanceus() # Bezpieczna wersja chmurowa (omija blokady USA)
    
    # ROZBUDOWANA WATCHLISTA DO MULTI-SKANOWANIA
    WATCHLISTA = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", 
        "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT"
    ]
    wielkosc_pozycji_usd = 25.0

    try:
        if st.session_state.aktywna_pozycja is None:
            for symbol in WATCHLISTA:
                swiece = gielda.fetch_ohlcv(symbol, timeframe="5m", limit=50)
                ceny = [s[4] for s in swiece]
                cena = ceny[-1]
                rsi = oblicz_rsi(ceny)
                
                # Zapis stanu do pamięci radaru
                st.session_state.aktualny_skan[symbol] = {"cena": cena, "rsi": rsi}
                
                # Kryterium zakupu SPOT (RSI poniżej 35 = wyprzedanie)
                if rsi < 35:
                    cena_tp = cena * 1.004
                    cena_sl = cena * 0.996
                    ilosc = wielkosc_pozycji_usd / cena
                    
                    st.session_state.aktywna_pozycja = {
                        'symbol': symbol, 'wejscie': cena,
                        'tp': cena_tp, 'sl': cena_sl, 'ilosc': ilosc
                    }
                    dodaj_log(f"🚨 [SYGNAŁ] Wykryto wyprzedanie na {symbol}. Wirtualny zakup.")
                    break 
                time.sleep(0.2) # Mikro-przerwa między monetami dla ochrony API

        else:
            pos = st.session_state.aktywna_pozycja
            ticker = gielda.fetch_ticker(pos['symbol'])
            obecna_cena = ticker['last']
            
            # Aktualizacja ceny na radarze podczas trwania pozycji
            if pos['symbol'] in st.session_state.aktualny_skan:
                st.session_state.aktualny_skan[pos['symbol']]['cena'] = obecna_cena
            
            if obecna_cena >= pos['tp']:
                zysk = (pos['tp'] - pos['wejscie']) * pos['ilosc']
                st.session_state.wirtualne_usdt += zysk
                st.session_state.historia_zagran.insert(0, {
                    "Data Zamknięcia": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Kryptowaluta": pos['symbol'].replace("/USDT", ""), 
                    "Status": "✅ TAKE PROFIT",
                    "Cena Wejścia": round(pos['wejscie'], 4), 
                    "Cena Wyjścia": round(obecna_cena, 4),
                    "Wynik USD": f"+{round(zysk, 2)}"
                })
                dodaj_log(f"🎉 Zamknięto {pos['symbol']} na poziomie Take Profit!")
                st.session_state.aktywna_pozycja = None

            elif obecna_cena <= pos['sl']:
                strata = (pos['wejscie'] - pos['sl']) * pos['ilosc']
                st.session_state.wirtualne_usdt -= strata
                st.session_state.historia_zagran.insert(0, {
                    "Data Zamknięcia": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Kryptowaluta": pos['symbol'].replace("/USDT", ""), 
                    "Status": "❌ STOP LOSS",
                    "Cena Wejścia": round(pos['wejscie'], 4), 
                    "Cena Wyjścia": round(obecna_cena, 4),
                    "Wynik USD": f"-{round(strata, 2)}"
                })
                dodaj_log(f"📉 Wybito Stop Loss dla pozycji {pos['symbol']}.")
                st.session_state.aktywna_pozycja = None

    except Exception as e:
        dodaj_log(f"⚠️ Problem z pobraniem danych: {str(e)}")

# =====================================================================
# PANEL STEROWANIA (SIDEBAR)
# =====================================================================
with st.sidebar:
    st.header("⚙️ Panel Sterowania")
    
    if st.button("▶️ URUCHOM BOTA", type="primary", use_container_width=True):
        if st.session_state.status_bota != "Uruchomiony":
            st.session_state.status_bota = "Uruchomiony"
            dodaj_log("Uruchamiam silnik skanujący Bybit/BinanceUS...")
            st.rerun()

    if st.button("🛑 ZATRZYMAJ", use_container_width=True):
        st.session_state.status_bota = "Wyłączony"
        dodaj_log("Bot został wyłączony przez użytkownika.")
        st.rerun()
        
    st.divider()
    status_kolor = "🟢" if st.session_state.status_bota == "Uruchomiony" else "🔴"
    st.markdown(f"**Status bota:** {status_kolor} {st.session_state.status_bota}")
    st.metric(label="💰 Kapitał Testowy", value=f"{round(st.session_state.wirtualne_usdt, 2)} USDT")

# =====================================================================
# GŁÓWNY INTERFEJS (DASHBOARD)
# =====================================================================
kol_radar, kol_pozycja = st.columns([1.6, 1])

with kol_radar:
    st.subheader("📡 Wielopoziomowy Radar Cyfrowy")
    if st.session_state.status_bota == "Uruchomiony" and len(st.session_state.aktualny_skan) == 0:
        st.info("🔄 Buduję mapę rynku rynkowego... Poczekaj ok. 10 sekund.")
    elif len(st.session_state.aktualny_skan) == 0:
        st.info("Radar jest nieaktywny. Odpal bota w menu bocznym.")
    else:
        # Dynamiczne budowanie siatki rzędów (po 4 kafelki w rzędzie)
        lista_monet = list(st.session_state.aktualny_skan.keys())
        for i in range(0, len(lista_monet), 4):
            wiersz_cols = st.columns(4)
            for j, symbol in enumerate(lista_monet[i:i+4]):
                dane = st.session_state.aktualny_skan[symbol]
                rsi_val = dane['rsi']
                kolor_delty = "inverse" if rsi_val < 35 else "normal"
                
                wiersz_cols[j].metric(
                    label=symbol.replace("/USDT", ""), 
                    value=f"{round(dane['cena'], 3)}", 
                    delta=f"RSI: {round(rsi_val, 1)}",
                    delta_color=kolor_delty
                )

with kol_pozycja:
    st.subheader("💼 Monitor Transakcji")
    pos = st.session_state.aktywna_pozycja
    if pos is None:
        st.success("Wszystkie wirtualne fundusze zabezpieczone w portfelu (USDT).")
    else:
        st.warning(f"🎰 **Pozycja na: {pos['symbol']}**")
        st.write(f"• Zakupiono po: `{round(pos['wejscie'], 4)}`")
        st.write(f"• Target Profit (TP): `{round(pos['tp'], 4)}`")
        st.write(f"• Stop Loss (SL): `{round(pos['sl'], 4)}`")

st.divider()

kol_logi, kol_historia = st.columns([1, 1.8])

with kol_logi:
    st.subheader("📋 Konsola Systemowa")
    logi_tekst = "\n".join(st.session_state.logi)
    st.text_area("Logi", value=logi_tekst, height=280, disabled=True, label_visibility="collapsed")

with kol_historia:
    st.subheader("📝 Dziennik Zamkniętych Zagrań")
    if not st.session_state.historia_zagran:
        st.info("Czekam na zamknięcie pierwszej transakcji algorytmicznej.")
    else:
        df = pd.DataFrame(st.session_state.historia_zagran)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # --- FUNKCJA GENEROWANIA PLIKU EXCEL/CSV ---
        csv_data = df.to_csv(index=False, sep=';').encode('utf-8')
        st.download_button(
            label="📥 Pobierz Dziennik Zagrań (.CSV dla Excela)",
            data=csv_data,
            file_name=f"dziennik_bota_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# =====================================================================
# PĘTLA PODTRZYMUJĄCA (Bezpieczne 10 sekund przerwy)
# =====================================================================
if st.session_state.status_bota == "Uruchomiony":
    skanuj_rynek()
    time.sleep(10) # 10 sekund odpoczynku – optymalna ochrona przed banem API
    st.rerun()
