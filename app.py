import io
import re
import urllib.request
import pandas as pd
import plotly.express as px
import streamlit as st

# 1. Konfiguracja globalna
st.set_page_config(
    page_title="System Raportowania Produkcji", page_icon="🏭", layout="wide"
)

# 2. Styling CSS dla menu nawigacyjnego
st.markdown(
    """
<style>
    /* Tło panelu bocznego */
    [data-testid="stSidebar"] {
        background-color: #fbe380 !important;
    }
    
    /* Nagłówek sekcji menu */
    .menu-header {
        font-size: 11px;
        font-weight: 800;
        color: #222222;
        letter-spacing: 1.5px;
        margin-bottom: 8px;
        margin-top: 10px;
        text-transform: uppercase;
    }

    /* Styl przycisków menu w panelu bocznym */
    [data-testid="stSidebar"] button {
        background-color: #fff8db !important;
        color: #222222 !important;
        border: 1.5px solid #222222 !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        margin-bottom: 6px !important;
        transition: all 0.2s ease !important;
    }
    
    /* Hover na przyciski */
    [data-testid="stSidebar"] button:hover {
        background-color: #222222 !important;
        color: #ffffff !important;
        border-color: #222222 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# 3. Nawigacja i stany sesji
if "active_module" not in st.session_state:
    st.session_state.active_module = "🏭 Obłożenie Maszyn"

with st.sidebar:
    st.markdown('<div class="menu-header">GŁÓWNE</div>', unsafe_allow_html=True)

    if st.button("🏭 Obłożenie Maszyn", use_container_width=True):
        st.session_state.active_module = "🏭 Obłożenie Maszyn"
        st.rerun()

    if st.button("🥩 Monitor Wędlin", use_container_width=True):
        st.session_state.active_module = "🥩 Monitor Wędlin"
        st.rerun()

    st.markdown("---")

wybor_modulu = st.session_state.active_module

# ==============================================================================
# MODUŁ 1: OBŁOŻENIE MASZYN
# ==============================================================================
if wybor_modulu == "🏭 Obłożenie Maszyn":
    st.title("🏭 System Monitorowania Obciążenia Parku Maszynowego")

    # ADRESY DANYCH GOOGLE SHEETS
    ID_OBCIAZENIE = "1vThuF2T2eI7hmHRtVEXAObE3oaCiDB46en9tqF_inZ4"  # Plan produkcyjny
    GID_OBCIAZENIE = "49369695"  # Zakładka Lech

    ID_WYDAJNOSC = "1Q-sZthoUPcF53A9XMNMlwRp1weZYzUxny0Rk-bxig9A"  # Plik z wydajnościami
    GID_WYDAJNOSC = "960305301"

    DOBOVA_DOSTEPNOSC_H = 20.0
    LIMIT_MAX_H = 24.0
    WAGA_SZTUKI_KG = 0.07

    def hours_to_hhmm(hours):
        if pd.isna(hours) or hours <= 0:
            return "0:00"
        total_minutes = int(round(hours * 60))
        h = total_minutes // 60
        m = total_minutes % 60
        return f"{h}:{m:02d}"

    @st.cache_data(ttl=300)
    def fetch_google_sheet(sheet_id, gid):
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        with urllib.request.urlopen(req) as response:
            csv_data = response.read()
        return pd.read_csv(io.BytesIO(csv_data))

    if st.sidebar.button("🔄 Odśwież dane maszyn"):
        st.cache_data.clear()
        st.rerun()

    try:
        with st.spinner("Pobieranie i przeliczanie danych maszyn z Google Sheets..."):
            df_wydajnosc_raw = fetch_google_sheet(ID_WYDAJNOSC, GID_WYDAJNOSC)
            df_obciazenie_raw = fetch_google_sheet(ID_OBCIAZENIE, GID_OBCIAZENIE)
        st.sidebar.success("✅ Pomyślnie pobrano dane maszyn")
    except Exception as e:
        st.sidebar.error(f"❌ Błąd pobierania danych: {e}")
        st.stop()

    # --- 1. Czyszczenie bazy wydajności ---
    df_wyd_raw = df_wydajnosc_raw.copy()
    df_wyd_raw.columns = df_wyd_raw.columns.astype(str).str.strip()

    col_maszyna_wyd = [c for c in df_wyd_raw.columns if "maszyna" in c.lower()][0]
    col_skladnik_wyd = [c for c in df_wyd_raw.columns if "składnik" in c.lower() or "danie" in c.lower() or "skladnik" in c.lower()][0]
    col_wyd_kg = [c for c in df_wyd_raw.columns if "wydajność" in c.lower() or "wydajnosc" in c.lower()][0]

    df_wyd = df_wyd_raw[[col_maszyna_wyd, col_skladnik_wyd, col_wyd_kg]].copy()
    df_wyd.columns = ["Maszyna", "Skladnik", "Wydajnosc_kg_h"]

    df_wyd["Maszyna"] = df_wyd["Maszyna"].astype(str).str.strip()
    df_wyd["Skladnik"] = df_wyd["Skladnik"].astype(str).str.strip()

    df_wyd["Wydajnosc_Efektywna"] = (
        df_wyd["Wydajnosc_kg_h"]
        .astype(str)
        .str.replace("kg/h", "", case=False)
        .str.replace("\xa0", "")
        .str.replace(" ", "")
        .str.replace(",", ".")
    )
    df_wyd["Wydajnosc_Efektywna"] = pd.to_numeric(df_wyd["Wydajnosc_Efektywna"], errors="coerce")
    df_wyd = df_wyd.dropna(subset=["Maszyna", "Wydajnosc_Efektywna"])

    wystepujace_maszyny = [
        m for m in sorted(df_wyd["Maszyna"].dropna().unique().tolist())
        if "brak maszyny" not in m.lower()
    ]

    # --- 2. Czyszczenie pliku z obciążeniem ---
    df_obc_raw = df_obciazenie_raw.copy()
    df_obc_raw.columns = df_obc_raw.columns.astype(str).str.strip()

    col_data_obc = [c for c in df_obc_raw.columns if "data produkcji" in c.lower() or "data menu" in c.lower()][0]
    col_skladnik_obc = [c for c in df_obc_raw.columns if "składnik" in c.lower() or "skladnik" in c.lower()][0]
    col_ilosc_obc = [c for c in df_obc_raw.columns if "zleceni" in c.lower() or "wyprodukowan" in c.lower() or "ilość" in c.lower()][0]
    col_maszyna_obc = [c for c in df_obc_raw.columns if "maszyna" in c.lower()][0]

    df_obc = df_obc_raw[[col_data_obc, col_skladnik_obc, col_ilosc_obc, col_maszyna_obc]].copy()
    df_obc.columns = ["Data", "Skladnik", "Ilosc", "Maszyna"]

    df_obc["Maszyna"] = df_obc["Maszyna"].astype(str).str.strip()
    df_obc["Skladnik"] = df_obc["Skladnik"].astype(str).str.strip()

    df_obc["Data"] = pd.to_datetime(df_obc["Data"], errors="coerce")
    df_obc = df_obc.dropna(subset=["Data"])
    df_obc = df_obc[df_obc["Data"].dt.year >= 2020]
    df_obc["Data_Date"] = df_obc["Data"].dt.date

    df_obc["Is_Szt"] = df_obc["Ilosc"].astype(str).str.contains("szt", case=False, na=False)
    df_obc["Ilosc"] = (
        df_obc["Ilosc"]
        .astype(str)
        .str.replace("kg", "", case=False)
        .str.replace("szt", "", case=False)
        .str.replace("\xa0", "")
        .str.replace(" ", "")
        .str.replace(",", ".")
    )
    df_obc["Ilosc"] = pd.to_numeric(df_obc["Ilosc"], errors="coerce")
    
    df_obc = df_obc[
        ~df_obc["Maszyna"].astype(str).str.lower().isin(["nan", "none", "", "nan", "praca ręczna / brak maszyny"])
    ]
    df_obc = df_obc.dropna(subset=["Data_Date", "Ilosc", "Maszyna"])

    for m in df_obc["Maszyna"].unique():
        if m not in wystepujace_maszyny and "brak maszyny" not in m.lower():
            wystepujace_maszyny.append(m)
    wystepujace_maszyny = sorted(list(set(wystepujace_maszyny)))

    # --- 3. Przeliczanie godzin ---
    df_merged = df_obc.merge(df_wyd, on=["Skladnik", "Maszyna"], how="left")

    def calculate_hours(row):
        ilosc = row["Ilosc"]
        wydajnosc = row["Wydajnosc_Efektywna"]
        is_szt = row["Is_Szt"]

        if pd.isna(wydajnosc) or wydajnosc == 0:
            return 0.0

        if is_szt:
            ilosc_kg = ilosc * WAGA_SZTUKI_KG
            return ilosc_kg / wydajnosc
        else:
            return ilosc / wydajnosc

    df_merged["ZaplanowaneGodziny_h"] = df_merged.apply(calculate_hours, axis=1)
    df_daily_sum = df_merged.groupby(["Data_Date", "Maszyna"])["ZaplanowaneGodziny_h"].sum().reset_index()

    wszystkie_daty = sorted([d for d in df_obc["Data_Date"].unique() if pd.notna(d)])
    full_index = (
        pd.MultiIndex.from_product(
            [wszystkie_daty, wystepujace_maszyny], names=["Data_Date", "Maszyna"]
        )
        .to_frame()
        .reset_index(drop=True)
    )

    df_daily_load = full_index.merge(df_daily_sum, on=["Data_Date", "Maszyna"], how="left")
    df_daily_load["ZaplanowaneGodziny_h"] = df_daily_load["ZaplanowaneGodziny_h"].fillna(0.0)

    df_daily_load["Data"] = pd.to_datetime(df_daily_load["Data_Date"])
    df_daily_load = df_daily_load.sort_values(by="Data")

    df_daily_load["Czas_produkcji"] = df_daily_load["ZaplanowaneGodziny_h"].apply(hours_to_hhmm)
    df_daily_load["Data_Format"] = df_daily_load["Data"].dt.strftime("%d.%m.%Y")

    def assign_status(row):
        if row["ZaplanowaneGodziny_h"] > DOBOVA_DOSTEPNOSC_H:
            return "PRZECIĄŻENIE (>20:00)"
        elif row["ZaplanowaneGodziny_h"] < 4.0:
            return "ZASTÓJ (<04:00)"
        return "Norma (04:00 - 20:00)"

    df_daily_load["Status"] = df_daily_load.apply(assign_status, axis=1)

    # ZAKŁADKI MODUŁU MASZYN
    tab_day, tab_range = st.tabs(["📅 Podgląd Dzienny", "📊 Zakres Dat dla Maszyny"])

    # --- ZAKŁADKA 1: PODGLĄD DZIENNY ---
    with tab_day:
        available_dates = sorted([d for d in df_daily_load["Data_Date"].unique() if pd.notna(d)])
        if available_dates:
            selected_date = st.selectbox("Wybierz dzień podglądu:", available_dates, key="day_select")
            df_day = df_daily_load[df_daily_load["Data_Date"] == selected_date]

            st.subheader(f"⚠️ Czas obciążenia maszyn w dniu: {selected_date}")

            color_map = {
                "PRZECIĄŻENIE (>20:00)": "#ef553b",
                "ZASTÓJ (<04:00)": "#ffa15a",
                "Norma (04:00 - 20:00)": "#636efa",
            }

            # 1. Wykres dla maszyn LECH
            df_lech = df_day[df_day["Maszyna"].astype(str).str.lower().str.startswith("lech")]
            if not df_lech.empty:
                st.markdown("### 🏭 Maszyny LECH")
                fig_lech = px.bar(
                    df_lech,
                    x="Maszyna",
                    y="ZaplanowaneGodziny_h",
                    color="Status",
                    color_discrete_map=color_map,
                    text="Czas_produkcji",
                    title=f"Liczba zaplanowanych godzin pracy maszyn LECH ({selected_date})",
                    custom_data=["Data_Format", "Czas_produkcji"],
                    labels={"ZaplanowaneGodziny_h": "Zaplanowany Czas [Godziny]"},
                )
                fig_lech.update_traces(
                    textposition="outside",
                    hovertemplate="<b>Maszyna:</b> %{x}<br>"
                    + "<b>Data:</b> %{customdata[0]}<br>"
                    + "<b>Czas produkcji:</b> %{customdata[1]}<extra></extra>",
                )
                fig_lech.add_hline(y=DOBOVA_DOSTEPNOSC_H, line_dash="solid", line_color="green", annotation_text="20:00:00")
                fig_lech.add_hline(y=LIMIT_MAX_H, line_dash="solid", line_color="red", annotation_text="24:00:00")
                fig_lech.update_xaxes(tickangle=-45)
                st.plotly_chart(fig_lech, use_container_width=True)

            st.markdown("---")

            # 2. Wykres dla maszyn H4
            df_h4 = df_day[df_day["Maszyna"].astype(str).str.lower().str.startswith("h4")]
            if not df_h4.empty:
                st.markdown("### 🏭 Maszyny H4")
                fig_h4 = px.bar(
                    df_h4,
                    x="Maszyna",
                    y="ZaplanowaneGodziny_h",
                    color="Status",
                    color_discrete_map=color_map,
                    text="Czas_produkcji",
                    title=f"Liczba zaplanowanych godzin pracy maszyn H4 ({selected_date})",
                    custom_data=["Data_Format", "Czas_produkcji"],
                    labels={"ZaplanowaneGodziny_h": "Zaplanowany Czas [Godziny]"},
                )
                fig_h4.update_traces(
                    textposition="outside",
                    hovertemplate="<b>Maszyna:</b> %{x}<br>"
                    + "<b>Data:</b> %{customdata[0]}<br>"
                    + "<b>Czas produkcji:</b> %{customdata[1]}<extra></extra>",
                )
                fig_h4.add_hline(y=DOBOVA_DOSTEPNOSC_H, line_dash="solid", line_color="green", annotation_text="20:00:00")
                fig_h4.add_hline(y=LIMIT_MAX_H, line_dash="solid", line_color="red", annotation_text="24:00:00")
                fig_h4.update_xaxes(tickangle=-45)
                st.plotly_chart(fig_h4, use_container_width=True)

            # ------------------------------------------------------------------------------
            # SZCZEGÓŁOWA ANALIZA PRZECIĄŻENIA (DRILL-DOWN DLA SKŁADNIKÓW)
            # ------------------------------------------------------------------------------
            st.divider()
            st.subheader("🔍 Szczegółowa analiza przeciążeń (Składniki / Zadania)")

            df_merged_day = df_merged[df_merged["Data_Date"] == selected_date].copy()
            overloaded_machines = df_day[df_day["ZaplanowaneGodziny_h"] > 20.0]["Maszyna"].tolist()

            if overloaded_machines:
                st.error(f"🚨 Wykryto przeciążenie dla maszyn: {', '.join(overloaded_machines)}")

                df_overloaded_details = df_merged_day[df_merged_day["Maszyna"].isin(overloaded_machines)].copy()

                df_breakdown = (
                    df_overloaded_details.groupby(["Maszyna", "Skladnik"])[["Ilosc", "ZaplanowaneGodziny_h"]]
                    .sum()
                    .reset_index()
                )
                df_breakdown["Czas_HHMM"] = df_breakdown["ZaplanowaneGodziny_h"].apply(hours_to_hhmm)
                df_breakdown = df_breakdown.sort_values(by="ZaplanowaneGodziny_h", ascending=False)

                fig_breakdown = px.bar(
                    df_breakdown,
                    x="Maszyna",
                    y="ZaplanowaneGodziny_h",
                    color="Skladnik",
                    title="Struktura czasowa składników na przeciążonych maszynach",
                    text="Czas_HHMM",
                    custom_data=["Skladnik", "Ilosc", "Czas_HHMM"],
                    labels={"ZaplanowaneGodziny_h": "Czas [Godziny]", "Skladnik": "Składnik / Produkcja"},
                )

                fig_breakdown.update_traces(
                    hovertemplate="<b>Składnik:</b> %{customdata[0]}<br>"
                    + "<b>Ilość:</b> %{customdata[1]} kg/szt<br>"
                    + "<b>Czas wykonania:</b> %{customdata[2]}<extra></extra>"
                )
                st.plotly_chart(fig_breakdown, use_container_width=True)

                with st.expander("📋 Tabela składników powodujących przeciążenie"):
                    st.dataframe(
                        df_breakdown[["Maszyna", "Skladnik", "Ilosc", "Czas_HHMM"]].rename(
                            columns={
                                "Skladnik": "Składnik / Danie",
                                "Ilosc": "Zaplanowana ilość",
                                "Czas_HHMM": "Wymagany czas",
                            }
                        ),
                        use_container_width=True,
                    )
            else:
                st.success("✅ Brak przeciążonych maszyn w wybranym dniu.")

            st.divider()
            with st.expander("📋 Szczegółowa tabela danych"):
                st.dataframe(
                    df_day[["Data_Format", "Maszyna", "Czas_produkcji", "Status"]].rename(
                        columns={"Data_Format": "Data"}
                    ),
                    use_container_width=True,
                )

    # --- ZAKŁADKA 2: ZAKRES DAT DLA MASZYNY ---
    with tab_range:
        st.subheader("📊 Czas pracy maszyn w przedziale czasowym")

        all_dates = sorted([d for d in df_daily_load["Data_Date"].unique() if pd.notna(d)])
        all_machines = sorted(df_daily_load["Maszyna"].unique())

        col_f1, col_f2, col_f3 = st.columns(3)

        with col_f1:
            start_date = st.date_input("Data od:", min_value=min(all_dates), max_value=max(all_dates), value=min(all_dates), key="r_start")
        with col_f2:
            end_date = st.date_input("Data do:", min_value=min(all_dates), max_value=max(all_dates), value=max(all_dates), key="r_end")
        with col_f3:
            selected_machines = st.multiselect("Wybierz maszyny:", options=all_machines, default=all_machines[:1] if len(all_machines) >= 1 else all_machines, key="r_mach")

        df_range = df_daily_load[
            (df_daily_load["Data_Date"] >= start_date)
            & (df_daily_load["Data_Date"] <= end_date)
            & (df_daily_load["Maszyna"].isin(selected_machines))
        ].sort_values(by=["Maszyna", "Data"])

        if not df_range.empty:
            st.markdown("### 1. Obciążenie bezpośrednie (ze zlecenia)")
            fig_range_bar = px.bar(
                df_range,
                x="Data_Format",
                y="ZaplanowaneGodziny_h",
                color="Maszyna",
                barmode="group",
                text="Czas_produkcji",
                title=f"Obciążenie bezpośrednie maszyn od {start_date} do {end_date}",
                custom_data=["Maszyna", "Data_Format", "Czas_produkcji"],
                labels={"ZaplanowaneGodziny_h": "Zaplanowany Czas [Godziny]", "Data_Format": "Data"},
            )

            fig_range_bar.update_traces(
                textposition="outside",
                hovertemplate="<b>Maszyna:</b> %{customdata[0]}<br>"
                + "<b>Data:</b> %{customdata[1]}<br>"
                + "<b>Czas:</b> %{customdata[2]}<extra></extra>",
            )

            fig_range_bar.add_hline(y=DOBOVA_DOSTEPNOSC_H, line_dash="solid", line_color="green", annotation_text="20:00:00")
            fig_range_bar.add_hline(y=LIMIT_MAX_H, line_dash="solid", line_color="red", annotation_text="24:00:00")
            fig_range_bar.update_xaxes(tickangle=-45)
            st.plotly_chart(fig_range_bar, use_container_width=True)

            st.markdown("---")

            st.markdown("### 2. Obciążenie z przeniesieniem")

            carryover_rows = []

            for m in selected_machines:
                df_m = df_range[df_range["Maszyna"] == m].sort_values(by="Data").copy()
                carryover_hours = 0.0

                for idx, row in df_m.iterrows():
                    total_needed = row["ZaplanowaneGodziny_h"] + carryover_hours

                    if total_needed > 0:
                        effective_hours = min(total_needed, DOBOVA_DOSTEPNOSC_H)
                        carryover_hours = total_needed - effective_hours

                        carryover_rows.append({
                            "Maszyna": m,
                            "Data_Format": row["Data_Format"],
                            "Godziny": effective_hours,
                            "Czas_HHMM": hours_to_hhmm(effective_hours),
                        })
                    else:
                        carryover_hours = 0.0
                        carryover_rows.append({
                            "Maszyna": m,
                            "Data_Format": row["Data_Format"],
                            "Godziny": 0.0,
                            "Czas_HHMM": "0:00",
                        })

            if carryover_rows:
                df_carryover = pd.DataFrame(carryover_rows)

                fig_carryover = px.bar(
                    df_carryover,
                    x="Data_Format",
                    y="Godziny",
                    color="Maszyna",
                    barmode="group",
                    text="Czas_HHMM",
                    title="Obciążenie z przeniesieniem nadgodzin (Limit dobowy 20h)",
                    custom_data=["Maszyna", "Data_Format", "Czas_HHMM"],
                    labels={"Godziny": "Czas [Godziny]", "Data_Format": "Data"},
                )

                fig_carryover.update_traces(
                    textposition="outside",
                    hovertemplate="<b>Maszyna:</b> %{customdata[0]}<br>"
                    + "<b>Data:</b> %{customdata[1]}<br>"
                    + "<b>Czas z przeniesieniem:</b> %{customdata[2]}<extra></extra>",
                )

                fig_carryover.add_hline(y=DOBOVA_DOSTEPNOSC_H, line_dash="solid", line_color="green", annotation_text="20:00:00")
                fig_carryover.add_hline(y=LIMIT_MAX_H, line_dash="solid", line_color="red", annotation_text="24:00:00")
                fig_carryover.update_xaxes(tickangle=-45)
                st.plotly_chart(fig_carryover, use_container_width=True)

            with st.expander("📋 Tabela czasowa z wybranego okresu"):
                st.dataframe(
                    df_range[["Data_Format", "Maszyna", "Czas_produkcji", "Status"]].rename(columns={"Data_Format": "Data"}),
                    use_container_width=True,
                )
        else:
            st.info("Brak danych dla wybranego zakresu dat lub wybranych maszyn.")


# ==============================================================================
# MODUŁ 2: MONITOR ZUŻYCIA I PRODUKCJI WĘDLIN
# ==============================================================================
elif wybor_modulu == "🥩 Monitor Wędlin":
    st.title("🥩 Monitor Zużycia i Produkcji Wędlin")

    CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR6yPlBb1niDz6fkAVgCV-eaYi_BKCNfrOjZcubp6cpwlujSryFN1bcPCmuFQhOuyZMM7pI4HBH8Zd3/pub?gid=1991174654&single=true&output=csv"

    @st.cache_data(ttl=300)
    def load_data_wedliny():
        req = urllib.request.Request(
            CSV_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        with urllib.request.urlopen(req) as response:
            csv_data = response.read()

        df = pd.read_csv(io.BytesIO(csv_data))
        if not any("Data" in str(col) for col in df.columns):
            df = pd.read_csv(io.BytesIO(csv_data), skiprows=1)

        df.columns = df.columns.astype(str).str.replace("#", "").str.strip()

        week_col = [c for c in df.columns if "tydzień" in c.lower() or "tydzien" in c.lower()]
        if week_col:
            df = df.rename(columns={week_col[0]: "Tydzień matrycy"})

        prognoza_col = None
        for col in df.columns:
            if "prognoza" in col.lower():
                prognoza_col = col
                break

        if not prognoza_col:
            st.error(f"Nie znaleziono kolumny 'prognoza'. Dostępne kolumny: {list(df.columns)}")
            st.stop()

        df = df.rename(columns={prognoza_col: "prognoza"})

        date_col = [c for c in df.columns if "Data" in c]
        if date_col:
            df = df.rename(columns={date_col[0]: "Data menu"})

        df["Data menu"] = pd.to_datetime(df["Data menu"], errors="coerce")
        df = df.dropna(subset=["Data menu"])

        df = df[df["Data menu"].dt.year >= 2020]

        df["prognoza"] = (
            df["prognoza"]
            .astype(str)
            .str.replace(",", ".")
            .str.replace(r"[^\d.]", "", regex=True)
        )
        df["prognoza"] = pd.to_numeric(df["prognoza"], errors="coerce").fillna(0.0)

        if "Tydzień matrycy" in df.columns:
            df["Tydzień matrycy"] = pd.to_numeric(df["Tydzień matrycy"], errors="coerce")
            df = df[df["Tydzień matrycy"].isin([1, 2, 3, 4])]
            df["Tydzień matrycy"] = df["Tydzień matrycy"].astype(int)

        return df

    try:
        df_w = load_data_wedliny()
    except Exception as e:
        st.error(f"Wystąpił błąd podczas pobierania danych wędlin: {e}")
        st.stop()

    st.sidebar.header("🔍 Filtry Wędlin")

    selected_weeks = []
    if "Tydzień matrycy" in df_w.columns:
        all_weeks = sorted(df_w["Tydzień matrycy"].unique().tolist())
        selected_weeks = st.sidebar.multiselect("Tydzień matrycy:", options=all_weeks, default=all_weeks)

    st.sidebar.subheader("📅 Zakres dat")
    min_date = df_w["Data menu"].min().date()
    max_date = df_w["Data menu"].max().date()

    col_date1, col_date2 = st.sidebar.columns(2)
    with col_date1:
        start_date_w = st.date_input("Data od:", value=min_date, min_value=min_date, max_value=max_date, key="w_start")
    with col_date2:
        end_date_w = st.date_input("Data do:", value=max_date, min_value=min_date, max_value=max_date, key="w_end")

    def get_unique_w(col_name):
        return sorted(df_w[col_name].dropna().unique().tolist()) if col_name in df_w.columns else []

    selected_products = st.sidebar.multiselect("Rodzaj produktu:", options=get_unique_w("RODZAJ PRODUKTU"), default=get_unique_w("RODZAJ PRODUKTU"))
    selected_diets = st.sidebar.multiselect("Dieta:", options=get_unique_w("DIETA/DATA"), default=get_unique_w("DIETA/DATA"))
    selected_meals = st.sidebar.multiselect("Posiłek:", options=get_unique_w("POSIŁEK"), default=get_unique_w("POSIŁEK"))

    filtered_df_w = df_w.copy()

    if "Tydzień matrycy" in filtered_df_w.columns and selected_weeks:
        filtered_df_w = filtered_df_w[filtered_df_w["Tydzień matrycy"].isin(selected_weeks)]

    if start_date_w and end_date_w:
        filtered_df_w = filtered_df_w[
            (filtered_df_w["Data menu"].dt.date >= start_date_w)
            & (filtered_df_w["Data menu"].dt.date <= end_date_w)
        ]

    if selected_products and "RODZAJ PRODUKTU" in filtered_df_w.columns:
        filtered_df_w = filtered_df_w[filtered_df_w["RODZAJ PRODUKTU"].isin(selected_products)]

    if selected_diets and "DIETA/DATA" in filtered_df_w.columns:
        filtered_df_w = filtered_df_w[filtered_df_w["DIETA/DATA"].isin(selected_diets)]

    if selected_meals and "POSIŁEK" in filtered_df_w.columns:
        filtered_df_w = filtered_df_w[filtered_df_w["POSIŁEK"].isin(selected_meals)]

    # Kafelki KPI
    col1, col2, col3, col4 = st.columns(4)
    total_kg = float(filtered_df_w["prognoza"].sum())
    unique_days = int(filtered_df_w["Data menu"].nunique())
    avg_daily_kg = float(total_kg / unique_days) if unique_days > 0 else 0.0

    top_product = "Brak"
    if "RODZAJ PRODUKTU" in filtered_df_w.columns and not filtered_df_w.empty:
        top_p = filtered_df_w.groupby("RODZAJ PRODUKTU")["prognoza"].sum()
        if not top_p.empty:
            top_product = top_p.idxmax()

    top_diet = "Brak"
    if "DIETA/DATA" in filtered_df_w.columns and not filtered_df_w.empty:
        top_d = filtered_df_w.groupby("DIETA/DATA")["prognoza"].sum()
        if not top_d.empty:
            top_diet = top_d.idxmax()

    col1.metric("Łączne zużycie", f"{total_kg:,.1f} kg".replace(",", " "))
    col2.metric("Średnio dziennie", f"{avg_daily_kg:,.1f} kg".replace(",", " "))
    col3.metric("Najpopularniejsza wędlina", top_product)
    col4.metric("Największa dieta", top_diet)

    st.divider()

    # Wykresy tygodniowe
    if "Tydzień matrycy" in filtered_df_w.columns and len(selected_weeks) > 1:
        st.header("⚖️ Porównanie Tygodni Matrycy")
        col_comp1, col_comp2 = st.columns(2)
        comp_df = filtered_df_w.copy()
        comp_df["Tydzień Etykieta"] = "Tydzień " + comp_df["Tydzień matrycy"].astype(str)

        with col_comp1:
            st.subheader("Porównanie zużycia produktów w poszczególnych tygodniach")
            week_prod = comp_df.groupby(["RODZAJ PRODUKTU", "Tydzień Etykieta"])["prognoza"].sum().reset_index()
            fig_week_comp = px.bar(
                week_prod,
                x="RODZAJ PRODUKTU",
                y="prognoza",
                color="Tydzień Etykieta",
                barmode="group",
                labels={"prognoza": "Suma (kg)", "RODZAJ PRODUKTU": "Wędlina", "Tydzień Etykieta": "Tydzień"},
                title="Zużycie produktów w podziale na Tygodnie Matrycy",
            )
            fig_week_comp.update_xaxes(tickangle=-45)
            st.plotly_chart(fig_week_comp, use_container_width=True)

        with col_comp2:
            st.subheader("Łączny tonaż w poszczególnych tygodniach")
            week_totals = comp_df.groupby("Tydzień Etykieta")["prognoza"].sum().reset_index().sort_values(by="Tydzień Etykieta")
            fig_week_totals = px.bar(
                week_totals,
                x="Tydzień Etykieta",
                y="prognoza",
                color="Tydzień Etykieta",
                text_auto=".1f",
                labels={"prognoza": "Suma łączna (kg)", "Tydzień Etykieta": "Tydzień"},
                title="Całkowite zużycie wędlin w każdym tygodniu",
            )
            st.plotly_chart(fig_week_totals, use_container_width=True)

        st.divider()

    # Wykresy szczegółowe
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("📆 Dziennie zużycie według produktów (kg)")
        if "RODZAJ PRODUKTU" in filtered_df_w.columns:
            daily_prod = filtered_df_w.groupby(["Data menu", "RODZAJ PRODUKTU"])["prognoza"].sum().reset_index()
            fig_daily = px.bar(
                daily_prod,
                x="Data menu",
                y="prognoza",
                color="RODZAJ PRODUKTU",
                labels={"prognoza": "Ilość (kg)", "Data menu": "Data"},
                barmode="stack",
            )
            fig_daily.update_xaxes(dtick="d1", tickformat="%Y-%m-%d")
            st.plotly_chart(fig_daily, use_container_width=True)

    with col_chart2:
        st.subheader("🏆 Ranking wędlin (Suma w kg)")
        if "RODZAJ PRODUKTU" in filtered_df_w.columns:
            top_wedliny = filtered_df_w.groupby("RODZAJ PRODUKTU")["prognoza"].sum().reset_index().sort_values(by="prognoza", ascending=True)
            fig_top = px.bar(
                top_wedliny,
                x="prognoza",
                y="RODZAJ PRODUKTU",
                orientation="h",
                labels={"prognoza": "Suma (kg)", "RODZAJ PRODUKTU": "Wędlina"},
                color="prognoza",
                color_continuous_scale="Viridis",
            )
            st.plotly_chart(fig_top, use_container_width=True)

    col_chart3, col_chart4 = st.columns(2)
    with col_chart3:
        st.subheader("🥗 Udział Diet w zużyciu")
        if "DIETA/DATA" in filtered_df_w.columns:
            diet_share = filtered_df_w.groupby("DIETA/DATA")["prognoza"].sum().reset_index()
            fig_diet = px.pie(diet_share, names="DIETA/DATA", values="prognoza", hole=0.4)
            st.plotly_chart(fig_diet, use_container_width=True)

    with col_chart4:
        st.subheader("🍳 Udział Posiłków")
        if "POSIŁEK" in filtered_df_w.columns:
            meal_share = filtered_df_w.groupby("POSIŁEK")["prognoza"].sum().reset_index()
            fig_meal = px.pie(meal_share, names="POSIŁEK", values="prognoza", hole=0.4)
            st.plotly_chart(fig_meal, use_container_width=True)

    st.divider()
    with st.expander("📄 Szczegółowa tabela przefiltrowanych danych"):
        st.dataframe(filtered_df_w, use_container_width=True)
        csv_export = filtered_df_w.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Pobierz dane jako CSV",
            data=csv_export,
            file_name="przefiltrowane_uzycie_wedlin.csv",
            mime="text/csv",
        )
