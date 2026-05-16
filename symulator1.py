import streamlit as st
import pandas as pd
import requests
import json

# Ustawienia strony dopasowane pod telefon
st.set_page_config(page_title="🤖 Panel Chmurowego Bota", layout="centered", initial_sidebar_state="collapsed")

# USTAW TUTAJ SWOJE DANE Z GITHUBA, ŻEBY STREAMLIT WIEDZIAŁ SKĄD CZYTAĆ
# Format URL: https://raw.githubusercontent.com/[TWÓJ_NICK]/[NAZWA_REPO]/main/stan_bota.json
NICK_GITHUB = "TUTAJ_WPISZ_SWÓJ_NICK_Z_GITHUB"
NAZWA_REPOZYTORIUM = "TUTAJ_WPISZ_NAZWĘ_REPA"

URL_STANU = f"https://raw.githubusercontent.com/{NICK_GITHUB}/{NAZWA_REPOZYTORIUM}/main/stan_bota.json"

st.title("🤖 Mobilny Monitor Bota")
st.caption("Dane odświeżają się automatycznie w tle na serwerach GitHub Actions co 10 minut.")

@st.cache_data(ttl=60) # Cache na 1 minutę, żeby nie bombardować GitHuba przy odświeżaniu strony
def pobierz_stan_z_chmury():
    try:
        response = requests.get(URL_STANU)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except:
        return None

stan = pobierz_stan_z_chmury()

if stan is None:
    st.error("❌ Nie udało się pobrać danych z GitHuba. Sprawdź czy poprawnie wpisałeś swój Nick i Nazwę repozytorium w pliku `streamlit_app.py` oraz czy plik `stan_bota.json` już powstał.")
else:
    # 1. GŁÓWNE STATYSTYKI (KAFELKI)
    saldo = stan.get("wirtualne_usdt", 100.0)
    zysk_procent = ((saldo - 100.0) / 100.0) * 100

    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Wirtualne Saldo", value=f"{round(saldo, 2)} USDT")
    with col2:
        st.metric(label="Całkowity Wynik", value=f"{round(zysk_procent, 2)}%", delta=f"{round(saldo-100.0, 2)} USD")

    st.markdown("---")

    # 2. SEKCJA AKTYWNEJ POZYCJI
    st.subheader("📈 Status Aktywnej Pozycji")
    pozycja = stan.get("aktywna_pozycja")

    if pozycja is None:
        st.info("😴 Obecnie bot nie posiada otwartej pozycji. Skanuje rynek w poszukiwaniu sygnału...")
    else:
        st.success(f"🚨 **OTWARTA POZYCJA: {pozycja['symbol']}**")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Cena Wejścia", f"{pozycja['wejscie']}")
        c2.metric("Target Profit (TP)", f"{round(pozycja['tp'], 4)}")
        c3.metric("Bieżący Stop Loss", f"{round(pozycja['aktualny_sl'], 4)}")
        
        # Pasek postępu podciągania stop lossa
        st.caption(f"Najwyższa odnotowana cena od zakupu: {pozycja['najwyzsza_cena']}")

    st.markdown("---")

    # 3. HISTORIA TRANSAKCJI
    st.subheader("📜 Dziennik Ostatnich Zagrań")
    historia = stan.get("historia_zagran", [])

    if not historia:
        st.text("Brak zamkniętych transakcji w historii.")
    else:
        df_historia = pd.DataFrame(historia)
        # Wyświetlamy jako ładną tabelę Streamlit
        st.dataframe(
            df_historia,
            column_config={
                "Wynik USD": st.column_config.TextColumn("Wynik Netto"),
                "Status": st.column_config.TextColumn("Typ Wyjścia")
            },
            hide_index=True,
            use_container_width=True
        )

    # Przycisk do ręcznego odświeżenia widoku na telefonie
    if st.button("🔄 Odśwież widok strony"):
        st.rerun()
