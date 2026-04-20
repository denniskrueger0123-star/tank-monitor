import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

st.set_page_config(layout="wide", page_title="N2 Tank Monitor v7")

st.title("🧊 Stickstofftank Monitor v7")

# ---------- Session State initialisieren ----------
if 'green_limit' not in st.session_state:
    st.session_state.green_limit = 60
if 'yellow_limit' not in st.session_state:
    st.session_state.yellow_limit = 30

# ---------- Speicherort fix neben Skript ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "claude_tank_log.csv")

# ---------- Daten laden ----------
if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
    if len(df) > 0:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date")
        
        # Spalte 'type' hinzufügen falls nicht vorhanden (Abwärtskompatibilität)
        if 'type' not in df.columns:
            df['type'] = 'normal'
else:
    df = pd.DataFrame(columns=["date", "level", "type"])

# ========== VERBRAUCHSRATE BERECHNEN (für Live-Prognose) ==========
avg_consumption = None
if len(df) >= 2:
    rates = []
    normal_df = df[df['type'] == 'normal'].copy()
    
    for i in range(1, len(normal_df)):
        d1 = normal_df.iloc[i-1]
        d2 = normal_df.iloc[i]
        
        days = (d2["date"] - d1["date"]).total_seconds() / 86400
        loss = d1["level"] - d2["level"]
        
        if days > 0 and loss > 0:
            rate = loss / days
            rates.append(rate)
    
    if rates:
        avg_consumption = sum(rates) / len(rates)

# ========== AKTUELLER STAND BERECHNEN (Live-Prognose) ==========
current_level_progn = None
last_measurement_date = None
is_prognosis = False

if len(df) > 0:
    last_entry = df.iloc[-1]
    last_measurement_date = last_entry["date"]
    last_measured_level = last_entry["level"]
    
    # Zeit seit letzter Messung
    time_since_last = (datetime.now() - last_measurement_date).total_seconds() / 86400
    
    # Wenn Verbrauchsrate bekannt ist und Zeit vergangen ist
    if avg_consumption and time_since_last > 0:
        # Prognose basierend auf Verlustrate
        estimated_loss = avg_consumption * time_since_last
        current_level_progn = max(last_measured_level - estimated_loss, 0)
        is_prognosis = True
    else:
        # Kein Verbrauch bekannt oder gerade erst gemessen
        current_level_progn = last_measured_level
        is_prognosis = False

# ========== 1. MESSWERT SPEICHERN ==========
st.header("📝 Messwert speichern")

# Zeige aktuelle Prognose als Vorschlag
if current_level_progn is not None and is_prognosis:
    st.info(f"💡 **Geschätzter aktueller Stand:** {current_level_progn:.1f}% "
            f"(basierend auf {time_since_last:.1f} Tagen seit letzter Messung)")

col1, col2 = st.columns([2, 1])

with col1:
    # Vorschlagswert ist die Prognose
    default_value = current_level_progn if current_level_progn is not None else 80.0
    
    new_level = st.number_input(
        "Tankstand (%)", 
        min_value=0.0, 
        max_value=100.0, 
        value=float(default_value),
        step=0.1,
        key="input_level"
    )

with col2:
    st.write("")
    st.write("")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("💧 Verlust", type="primary", use_container_width=True, help="Normaler Messwert (Verbrauch)"):
            new_entry = pd.DataFrame(
                [[datetime.now(), new_level, "normal"]],
                columns=["date", "level", "type"]
            )
            df = pd.concat([df, new_entry], ignore_index=True)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            df.to_csv(DATA_FILE, index=False)
            st.success("✅ Messwert gespeichert!")
            st.rerun()
    
    with col_btn2:
        if st.button("⛽ Nachgefüllt", type="secondary", use_container_width=True, help="Nachfüllung dokumentieren"):
            new_entry = pd.DataFrame(
                [[datetime.now(), new_level, "refill"]],
                columns=["date", "level", "type"]
            )
            df = pd.concat([df, new_entry], ignore_index=True)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            df.to_csv(DATA_FILE, index=False)
            st.success("⛽ Nachfüllung dokumentiert!")
            st.rerun()

st.divider()

# ========== 2. TANKANZEIGE ==========
if current_level_progn is not None:
    
    st.header("🎯 Tankanzeige")
    
    col_gauge1, col_gauge2 = st.columns([2, 1])
    
    with col_gauge1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=current_level_progn,
            title={'text': "Aktueller Füllstand (Prognose)" if is_prognosis else "Aktueller Füllstand", 
                   'font': {'size': 24}},
            delta={'reference': 100, 'suffix': '%'},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkgray"},
                'bar': {'color': "orange" if is_prognosis else "cyan", 'thickness': 0.75},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, st.session_state.yellow_limit], 'color': "rgba(255,0,0,0.3)"},
                    {'range': [st.session_state.yellow_limit, st.session_state.green_limit], 'color': "rgba(255,165,0,0.3)"},
                    {'range': [st.session_state.green_limit, 100], 'color': "rgba(0,255,0,0.2)"},
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': st.session_state.yellow_limit
                }
            }
        ))
        
        fig.update_layout(
            height=400,
            font={'size': 16}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col_gauge2:
        if is_prognosis:
            st.metric(
                "Prognostizierter Stand", 
                f"{current_level_progn:.1f}%",
                delta=f"-{(last_measured_level - current_level_progn):.1f}% (geschätzt)"
            )
            st.metric(
                "Letzte Messung", 
                last_measurement_date.strftime('%d.%m.%Y %H:%M'),
                delta=f"vor {time_since_last:.1f} Tagen"
            )
            st.warning("⏱️ **PROGNOSE**\nBasierend auf Verlustrate")
        else:
            st.metric("Letzter Messwert", f"{current_level_progn:.1f}%")
            st.metric("Zeitpunkt", last_measurement_date.strftime('%d.%m.%Y %H:%M'))
            
            last_type = df.iloc[-1]["type"]
            if last_type == "refill":
                st.info("⛽ Letzte Aktion: **Nachfüllung**")
            else:
                st.info("💧 Letzte Aktion: **Messwert**")
        
        # Visuelle Warnung
        if current_level_progn <= st.session_state.yellow_limit:
            st.error("🚨 **KRITISCH**\nSofort nachfüllen!")
        elif current_level_progn <= st.session_state.green_limit:
            st.warning("⚠️ **WARNUNG**\nBald nachfüllen")
        else:
            st.success("✅ **OK**\nSicherer Bereich")
    
    # Nachfüll-Statistik
    refills = df[df['type'] == 'refill']
    if len(refills) > 0:
        last_refill = refills.iloc[-1]
        days_since_refill = (datetime.now() - last_refill['date']).total_seconds() / 86400
        
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.metric(
                "Letzte Nachfüllung", 
                last_refill['date'].strftime('%d.%m.%Y %H:%M'),
                delta=f"vor {days_since_refill:.1f} Tagen"
            )
        with col_stat2:
            st.metric("Nachfüllungen gesamt", len(refills))
    
    st.divider()

# ========== 3. VERBRAUCHSANALYSE ==========
st.header("📊 Verbrauchsanalyse")

if len(df) >= 2:
    
    rates = []
    rate_dates = []
    
    # Nur normale Messwerte für Verbrauchsberechnung
    normal_df = df[df['type'] == 'normal'].copy()
    
    for i in range(1, len(normal_df)):
        d1 = normal_df.iloc[i-1]
        d2 = normal_df.iloc[i]
        
        days = (d2["date"] - d1["date"]).total_seconds() / 86400
        loss = d1["level"] - d2["level"]
        
        # Nur echten Verlust zählen
        if days > 0 and loss > 0:
            rate = loss / days
            rates.append(rate)
            rate_dates.append(d2["date"])
    
    if rates:
        avg_consumption = sum(rates) / len(rates)
        min_consumption = min(rates)
        max_consumption = max(rates)
        
        col_metric1, col_metric2, col_metric3 = st.columns(3)
        
        with col_metric1:
            st.metric("⌀ Verbrauch", f"{avg_consumption:.2f} %/Tag")
        
        with col_metric2:
            st.metric("Min Verbrauch", f"{min_consumption:.2f} %/Tag")
        
        with col_metric3:
            st.metric("Max Verbrauch", f"{max_consumption:.2f} %/Tag")
        
        # Prognose berechnen (mit prognostiziertem Wert)
        if current_level_progn is not None:
            
            days_to_green = (current_level_progn - st.session_state.green_limit) / avg_consumption if avg_consumption > 0 else 0
            days_to_yellow = (current_level_progn - st.session_state.yellow_limit) / avg_consumption if avg_consumption > 0 else 0
            days_to_empty = current_level_progn / avg_consumption if avg_consumption > 0 else 0
            
            # Prognose-Boxen
            col_prog1, col_prog2 = st.columns(2)
            
            with col_prog1:
                if days_to_green > 0:
                    green_date = datetime.now() + timedelta(days=days_to_green)
                    st.success(f"🟢 **Empfohlene Nachfüllung ({st.session_state.green_limit}%)**\n\n"
                              f"In ca. **{days_to_green:.1f} Tagen**\n\n"
                              f"📅 {green_date.strftime('%d.%m.%Y')}")
                else:
                    st.success(f"🟢 **Empfohlene Nachfüllung ({st.session_state.green_limit}%)**\n\n"
                              f"⚠️ Bereits erreicht!")
            
            with col_prog2:
                if days_to_yellow > 0:
                    yellow_date = datetime.now() + timedelta(days=days_to_yellow)
                    st.error(f"🔴 **Kritische Grenze ({st.session_state.yellow_limit}%)**\n\n"
                            f"In ca. **{days_to_yellow:.1f} Tagen**\n\n"
                            f"📅 {yellow_date.strftime('%d.%m.%Y')}")
                else:
                    st.error(f"🔴 **Kritische Grenze ({st.session_state.yellow_limit}%)**\n\n"
                            f"🚨 Bereits erreicht!")
            
            if days_to_empty > 0:
                empty_date = datetime.now() + timedelta(days=days_to_empty)
                st.warning(f"📉 **Tank komplett leer** in ca. **{days_to_empty:.1f} Tagen** ({empty_date.strftime('%d.%m.%Y')})")
        
        st.subheader("Verbrauchsrate über Zeit")
        
        fig_rate = go.Figure()
        
        # Verbrauchslinie
        fig_rate.add_trace(go.Scatter(
            x=rate_dates,
            y=rates,
            mode="lines+markers",
            name="Verbrauchsrate",
            line=dict(color='rgb(31,119,180)', width=3),
            marker=dict(size=8, line=dict(width=2, color='white'))
        ))
        
        # Durchschnittslinie
        fig_rate.add_trace(go.Scatter(
            x=rate_dates,
            y=[avg_consumption] * len(rate_dates),
            mode="lines",
            name="Ø Verbrauch",
            line=dict(color='red', width=2, dash='dash')
        ))
        
        fig_rate.update_layout(
            xaxis_title="Datum",
            yaxis_title="Verbrauchsrate (%/Tag)",
            hovermode='x unified',
            height=400,
            yaxis=dict(range=[0, max(rates) * 1.2])
        )
        
        st.plotly_chart(fig_rate, use_container_width=True)
        
        # Tankverlauf mit Prognose
        st.subheader("Tankverlauf mit Prognose")
        
        fig_forecast = go.Figure()
        
        # Historischer Verlauf
        fig_forecast.add_trace(go.Scatter(
            x=df["date"],
            y=df["level"],
            mode="lines+markers",
            name="Ist-Verlauf",
            line=dict(color='rgb(31,119,180)', width=3),
            marker=dict(size=8, line=dict(width=2, color='white'))
        ))
        
        # Nachfüllungen markieren
        refill_data = df[df['type'] == 'refill']
        if len(refill_data) > 0:
            fig_forecast.add_trace(go.Scatter(
                x=refill_data["date"],
                y=refill_data["level"],
                mode="markers",
                name="Nachfüllung",
                marker=dict(
                    size=15, 
                    color='rgb(0,200,0)', 
                    symbol='triangle-up',
                    line=dict(width=2, color='white')
                )
            ))
        
        # Live-Prognose Punkt (JETZT)
        if is_prognosis:
            fig_forecast.add_trace(go.Scatter(
                x=[datetime.now()],
                y=[current_level_progn],
                mode="markers",
                name="Prognose JETZT",
                marker=dict(
                    size=15,
                    color='orange',
                    symbol='star',
                    line=dict(width=2, color='white')
                )
            ))
        
        # Prognose-Linie in die Zukunft
        if current_level_progn > st.session_state.yellow_limit and days_to_yellow > 0:
            forecast_dates = []
            forecast_levels = []
            
            current_date = datetime.now()
            forecast_dates.append(current_date)
            forecast_levels.append(current_level_progn)
            
            if days_to_yellow > 0:
                yellow_date = current_date + timedelta(days=days_to_yellow)
                forecast_dates.append(yellow_date)
                forecast_levels.append(st.session_state.yellow_limit)
            
            if days_to_empty > 0:
                empty_date = current_date + timedelta(days=days_to_empty)
                forecast_dates.append(empty_date)
                forecast_levels.append(0)
            
            fig_forecast.add_trace(go.Scatter(
                x=forecast_dates,
                y=forecast_levels,
                mode="lines",
                name="Prognose",
                line=dict(color='rgba(255,165,0,0.6)', width=3, dash='dot')
            ))
        
        # Grenzlinien
        fig_forecast.add_hline(
            y=st.session_state.green_limit, 
            line_dash="dash", 
            line_color="green",
            line_width=2,
            annotation_text=f"🟢 Empfohlen nachfüllen ({st.session_state.green_limit}%)",
            annotation_position="right"
        )
        
        fig_forecast.add_hline(
            y=st.session_state.yellow_limit, 
            line_dash="dash", 
            line_color="red",
            line_width=2,
            annotation_text=f"🔴 Kritisch ({st.session_state.yellow_limit}%)",
            annotation_position="right"
        )
        
        # Bereiche einfärben
        fig_forecast.add_hrect(
            y0=st.session_state.green_limit, 
            y1=100,
            fillcolor="green", 
            opacity=0.1,
            line_width=0
        )
        
        fig_forecast.add_hrect(
            y0=st.session_state.yellow_limit, 
            y1=st.session_state.green_limit,
            fillcolor="orange", 
            opacity=0.1,
            line_width=0
        )
        
        fig_forecast.add_hrect(
            y0=0, 
            y1=st.session_state.yellow_limit,
            fillcolor="red", 
            opacity=0.1,
            line_width=0
        )
        
        fig_forecast.update_layout(
            xaxis_title="Datum",
            yaxis_title="Tankstand (%)",
            hovermode='x unified',
            height=500,
            yaxis=dict(range=[0, 105])
        )
        
        st.plotly_chart(fig_forecast, use_container_width=True)
        
    else:
        st.info("ℹ️ Noch nicht genug Daten für Verbrauchsanalyse (mindestens 2 normale Messwerte mit Verlust nötig)")

else:
    st.info("ℹ️ Noch nicht genug Daten (mindestens 2 Messwerte nötig)")

st.divider()

# ========== 4. WARNAMPEL EINSTELLUNGEN ==========
st.header("⚙️ Warnampel Einstellungen")

col_warn1, col_warn2 = st.columns(2)

with col_warn1:
    green_limit = st.slider(
        "🟢 Empfohlen nachfüllen ab (%)", 
        min_value=40, 
        max_value=100, 
        value=st.session_state.green_limit,
        help="Tankstand gilt als sicher ab diesem Wert - empfohlener Nachfüllzeitpunkt"
    )

with col_warn2:
    yellow_limit = st.slider(
        "🔴 Kritisch unter (%)", 
        min_value=5, 
        max_value=60, 
        value=st.session_state.yellow_limit,
        help="Tankstand gilt als kritisch unter diesem Wert - sofort nachfüllen!"
    )

# Session State aktualisieren
if green_limit != st.session_state.green_limit or yellow_limit != st.session_state.yellow_limit:
    st.session_state.green_limit = green_limit
    st.session_state.yellow_limit = yellow_limit
    st.rerun()

# Validierung
if yellow_limit >= green_limit:
    st.error("⚠️ Kritischer Wert muss unter dem empfohlenen Nachfüllwert liegen!")

st.divider()

# ========== 5. ROHDATEN ==========
st.header("📋 Rohdaten verwalten")

# CSV Import
uploaded_file = st.file_uploader(
    "📁 CSV-Datei importieren", 
    type="csv",
    help="Importiere eine bestehende claude_tank_log.csv Datei"
)

if uploaded_file is not None:
    try:
        imported_df = pd.read_csv(uploaded_file)
        imported_df["date"] = pd.to_datetime(imported_df["date"], errors="coerce")
        imported_df = imported_df.dropna(subset=["date"])
        
        # Spalte 'type' hinzufügen falls nicht vorhanden
        if 'type' not in imported_df.columns:
            imported_df['type'] = 'normal'
        
        # Mit bestehenden Daten zusammenführen
        df = pd.concat([df, imported_df], ignore_index=True)
        df = df.drop_duplicates(subset=["date"])
        df = df.sort_values("date")
        
        df.to_csv(DATA_FILE, index=False)
        st.success(f"✅ {len(imported_df)} Einträge importiert!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Fehler beim Import: {e}")

# Daten bearbeiten
st.subheader("Daten bearbeiten")

if len(df) > 0:
    
    # DataFrame für Anzeige vorbereiten
    display_df = df.copy()
    display_df["date"] = display_df["date"].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    edited_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "date": st.column_config.TextColumn(
                "Datum & Uhrzeit",
                help="Format: YYYY-MM-DD HH:MM:SS",
                width="medium"
            ),
            "level": st.column_config.NumberColumn(
                "Tankstand (%)",
                min_value=0,
                max_value=100,
                step=0.1,
                format="%.1f %%"
            ),
            "type": st.column_config.SelectboxColumn(
                "Typ",
                options=["normal", "refill"],
                help="normal = Messwert, refill = Nachfüllung",
                width="small"
            )
        }
    )
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("💾 Änderungen speichern", use_container_width=True):
            try:
                edited_df["date"] = pd.to_datetime(edited_df["date"], errors="coerce")
                edited_df = edited_df.dropna(subset=["date"])
                edited_df = edited_df.sort_values("date")
                
                # Sicherstellen dass type-Spalte existiert
                if 'type' not in edited_df.columns:
                    edited_df['type'] = 'normal'
                
                edited_df.to_csv(DATA_FILE, index=False)
                st.success("✅ Änderungen gespeichert!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Fehler beim Speichern: {e}")
    
    with col_btn2:
        # CSV Export
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 CSV exportieren",
            data=csv_data,
            file_name=f"claude_tank_log_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col_btn3:
        if st.button("🗑️ Alle Daten löschen", use_container_width=True, type="secondary"):
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
                st.warning("⚠️ Alle Daten gelöscht!")
                st.rerun()

else:
    st.info("ℹ️ Noch keine Daten vorhanden")

st.caption("💾 Daten werden lokal in `claude_tank_log.csv` gespeichert | 💧 Verlust = normaler Messwert | ⛽ Nachfüllung wird separat dokumentiert | ⏱️ Live-Prognose basierend auf Verlustrate")
