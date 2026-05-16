import streamlit as st
import ccxt
import time
import pandas as pd
import pandas_ta as ta
from datetime import datetime

# =====================================================================
# KONFIGURACJA STRONY
# =====================================================================
st.set_page_config(page_title="Quant Bot SPOT V1", layout="wide", page_icon="🤖")

st.title("🤖 Quant Dashboard: Autonomiczny Bot SPOT")
st.markdown("---")

# Inicjalizacja pamięci podręcznej (Session State)
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

# =====================================================================
# LOGIKA ZAAWANSOWANEGO SKANERA
# =====================================================================
def skanuj_rynek():
    # Używamy Binance US, aby ominąć geoblokady chmury Streamlit (dla USA)
    gielda = ccxt.binanceus()
    
    # PEŁNA LISTA 10 KRYPTOWALUT
    WATCHLISTA = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", 
        "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT", "LTC/USDT"
    ]
    wielkosc_pozycji_usd = 25.0

    try:
        # PRZYPADEK 1: BRAK POZYCJI -> SZUKAMY ZŁOTEGO SYGNAŁU
        if st.session_state.aktywna_pozycja is None:
            for symbol in WATCHLISTA:
                # Pobieramy 100 świec dla precyzyjnego obliczenia EMA i MACD
                swiece = gielda.fetch_ohlcv(symbol, timeframe="5m", limit=100)
                
                df = pd.DataFrame(swiece, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # 🚀 OBLICZANIE WSKAŹNIKÓW (pandas_ta)
                df.ta.ema(length=9, append=True)
                df.ta.macd(fast=12, slow=26, signal=9, append=True)
                df.ta.rsi(length=14, append=True)
                df.ta.atr(length=14, append=True)
                df['v_avg'] = df['volume'].rolling(20).mean() # Średni wolumen
                
                # Zabezpieczenie przed brakami na początku kalkulacji
                if df.isna().iloc[-1].any():
                    continue

                # OSTATNIE WARTOŚCI
                cena = df['close'].iloc[-1]
                rsi = df['RSI_14'].iloc[-1]
                ema9 = df['EMA_9'].iloc[-1]
                macd_h = df['MACDh_12_26_9'].iloc[-1]
                macd_h_prev = df['MACDh_12_26_9'].iloc[-2]
                vol = df['volume'].iloc[-1]
                v_avg = df['v_avg'].iloc[-1]
                atr = df['ATRr_14'].iloc[-1]
                
                # Zapis do radaru (dla wizualizacji)
                st.session_state.aktualny_skan[symbol] = {
                    "cena": cena, "rsi": rsi, "ema_przebita": cena > ema9
                }
                
                # 🛡️ ZŁOTY WARUNEK WEJŚCIA
                warunek_tani = rsi < 45  
                warunek_odbicia = cena > ema9  
                warunek_momentum = macd_h > macd_h_prev  
                warunek_wolumenu = vol > v_avg  
                
                if warunek_tani and warunek_odbicia and warunek_momentum and warunek_wolumenu:
                    odleglosc_atr = atr * 1.5  # SL jest oddalony o 1.5-krotność obecnej zmienności ATR
                    poczatkowy_sl = cena - odleglosc_atr
                    cena_tp = cena * 1.015  # Twardy cel (+1.5%)
                    ilosc = wielkosc_pozycji_usd / cena
                    
                    st.session_state.aktywna_pozycja = {
                        'symbol': symbol, 
                        'wejscie': cena,
                        'najwyzsza_cena': cena, 
                        'tp': cena_tp, 
                        'aktualny_sl': poczatkowy_sl, 
                        'odleglosc_tsl': odleglosc_atr, 
                        'ilosc': ilosc
                    }
                    dodaj_log(f"🚨 [ZŁOTY SYGNAŁ] Wykryto bezpieczne odbicie na {symbol}! RSI: {round(rsi,1)}")
                    break 
                time.sleep(0.2)

        # PRZYPADEK 2: POZYCJA OTWARTA -> ŚLEDZIMY ATR TRAILING SL
        else:
            pos = st.session_state.aktywna_pozycja
            ticker = gielda.fetch_ticker(pos['symbol'])
            obecna_cena = ticker['last']
            
            if pos['symbol'] in st.session_state.aktualny_skan:
                st.session_state.aktualny_skan[pos['symbol']]['cena'] = obecna_cena

            # --- RUCHOMY ATR STOP LOSS ---
            if obecna_cena > pos['najwyzsza_cena']:
                pos['najwyzsza_cena'] = obecna_cena
                nowy_sl = obecna_cena - pos['odleglosc_tsl']
                if nowy_sl > pos['aktualny_sl']:
                    pos['aktualny_sl'] = nowy_sl
            
            # --- EGZEKUCJA ZAMKNIĘCIA ---
            # 1. Awaryjny Take Profit (Wystrzał w górę)
            if obecna_cena >= pos['tp']:
                zysk = (pos['tp'] - pos['wejscie']) * pos['ilosc']
                st.session_state.wirtualne_usdt += zysk
                st.session_state.historia_zagran.insert(0, {
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Moneta": pos['symbol'].replace("/USDT", ""), "Status": "🚀 TWARDY TP",
                    "Wejście": round(pos['wejscie'], 4), "Wyjście": round(obecna_cena, 4),
                    "Wynik USD": f"+{round(zysk, 2)}"
                })
                dodaj_log(f"🎉 Zamknięto {pos['symbol']} na Twardym Take Profit (+1.5%)!")
                st.session_state.aktywna_pozycja = None

            # 2. Wybicie na Trailing Stop Loss
            elif obecna_cena <= pos['aktualny_sl']:
                wynik_netto = (pos['aktualny_sl'] - pos['wejscie']) * pos['ilosc']
                st.session_state.wirtualne_usdt += wynik_netto
                
                status_txt = "✅ ZYSKOWNY ATR-SL" if wynik_netto > 0 else "❌ STRATNY ATR-SL"
                znak = "+" if wynik_netto > 0 else ""
                
                st.session_state.historia_zagran.insert(0, {
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Moneta": pos['symbol'].replace("/USDT", ""), "Status": status_txt,
                    "Wejście": round(pos['wejscie'], 4), "Wyjście": round(pos['aktualny_sl'], 4),
                    "Wynik USD": f"{znak}{round(wynik_netto, 2)}"
                })
                dodaj_log(f"🛡️ Zamek ATR wyzwolony dla {pos['symbol']}. Wynik: {znak}{round(wynik_netto, 2)} USD.")
                st.session_state.aktywna_pozycja = None

    except Exception as e:
        dodaj_log(f"⚠️ Chwilowy błąd sieci, ponawiam analizę...")

# =====================================================================
# INTERFEJS
# =====================================================================
with st.sidebar:
    st.header("⚙️ Panel Sterowania")
    
    if st.button("▶️ URUCHOM BOTA", type="primary", use_container_width=True):
        if st.session_state.status_bota != "Uruchomiony":
            st.session_state.status_bota = "Uruchomiony"
            dodaj_log("Uruchamiam silnik Quant. Inicjalizacja EMA/MACD/ATR...")
            st.rerun()

    if st.button("🛑 ZATRZYMAJ", use_container_width=True):
        st.session_state.status_bota = "Wyłączony"
        dodaj_log("System zatrzymany.")
        st.rerun()
        
    st.divider()
    status_kolor = "🟢" if st.session_state.status_bota == "Uruchomiony" else "🔴"
    st.markdown(f"**Status:** {status_kolor} {st.session_state.status_bota}")
    st.metric(label="💰 Kapitał (USDT)", value=f"{round(st.session_state.wirtualne_usdt, 2)}")

kol_radar, kol_pozycja = st.columns([1.8, 1])

with kol_radar:
    st.subheader("📡 Radar Algorytmiczny (5m)")
    if st.session_state.status_bota == "Uruchomiony" and len(st.session_state.aktualny_skan) == 0:
        st.info("🔄 Przeliczam dane historyczne dla 10 rynków. To potrwa ok. 15 sekund...")
    elif len(st.session_state.aktualny_skan) == 0:
        st.info("Radar jest nieaktywny.")
    else:
        # PRAWIDŁOWY UKŁAD: 4 kolumny (żeby zapobiec ucinaniu liczb na BTC/ETH)
        lista_monet = list(st.session_state.aktualny_skan.keys())
        for i in range(0, len(lista_monet), 4):
            wiersz_cols = st.columns(4)
            for j, symbol in enumerate(lista_monet[i:i+4]):
                dane = st.session_state.aktualny_skan[symbol]
                
                ema_znaczek = "✔️EMA" if dane['ema_przebita'] else "❌EMA"
                kolor_delty = "inverse" if dane['rsi'] < 45 else "normal"
                
                # Zabezpieczenie przed długimi liczbami
                cena = dane['cena']
                cena_str = f"{int(cena)}" if cena > 1000 else f"{round(cena, 3)}"
                
                wiersz_cols[j].metric(
                    label=symbol.replace("/USDT", ""), 
                    value=cena_str, 
                    delta=f"RSI:{round(dane['rsi'], 1)} {ema_znaczek}",
                    delta_color=kolor_delty
                )

with kol_pozycja:
    st.subheader("💼 Monitor Transakcji (ATR Trailing SL)")
    pos = st.session_state.aktywna_pozycja
    if pos is None:
        st.success("Szukam Złotego Sygnału. Wymagane potwierdzenie EMA9, MACD i Wolumenu.")
    else:
        st.warning(f"🎰 **Pozycja otwarta: {pos['symbol']}**")
        st.write(f"💵 Wejście po cenie: `{round(pos['wejscie'], 4)}`")
        st.write(f"📈 Osiągnięty szczyt: `{round(pos['najwyzsza_cena'], 4)}`")
        st.write(f"🛡️ **Obecny bufor obronny SL:** `{round(pos['aktualny_sl'], 4)}`")
        
        zabezpieczony_wynik = (pos['aktualny_sl'] - pos['wejscie']) / pos['wejscie'] * 100
        kolor_tekstu = "green" if zabezpieczony_wynik > 0 else "red"
        st.markdown(f"Gwarantowany wynik po wbiciu SL: <span style='color:{kolor_tekstu}; font-weight:bold;'>{round(zabezpieczony_wynik, 2)}%</span>", unsafe_allow_html=True)

st.divider()

kol_logi, kol_historia = st.columns([1, 1.8])

with kol_logi:
    st.subheader("📋 Konsola Logów")
    logi_tekst = "\n".join(st.session_state.logi)
    st.text_area("Zdarzenia", value=logi_tekst, height=280, disabled=True, label_visibility="collapsed")

with kol_historia:
    st.subheader("📝 Dziennik Excel (Zabezpieczone Transakcje)")
    if not st.session_state.historia_zagran:
        st.info("Brak zamkniętych transakcji.")
    else:
        df = pd.DataFrame(st.session_state.historia_zagran)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        csv_data = df.to_csv(index=False, sep=';').encode('utf-8')
        st.download_button(
            label="📥 Pobierz CSV", data=csv_data,
            file_name=f"forward_test_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv", use_container_width=True
        )

# =====================================================================
# PĘTLA PODTRZYMUJĄCA
# =====================================================================
if st.session_state.status_bota == "Uruchomiony":
    skanuj_rynek()
    time.sleep(12) 
    st.rerun()
