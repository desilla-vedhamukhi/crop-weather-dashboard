import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import date

st.set_page_config(page_title="Crop & Weather Dashboard", page_icon="🌾",
                   layout="wide", initial_sidebar_state="collapsed")

# ---------------- Mobile-friendly styling ----------------
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-left: 1rem; padding-right: 1rem;}
.advice-box {padding: 18px; border-radius: 14px; color: white; margin-bottom: 10px;}
.advice-title {font-size: 28px; font-weight: 700; margin: 0;}
.advice-text {font-size: 17px; margin: 6px 0 0 0;}
@media (max-width: 640px) {
    h1 {font-size: 1.6rem !important;}
    .advice-title {font-size: 22px;}
    .advice-text {font-size: 15px;}
    [data-testid="stMetricValue"] {font-size: 1.2rem;}
}
</style>
""", unsafe_allow_html=True)

# ---------------- Config ----------------
LOCATIONS = {
    "Guntur, AP": (16.31, 80.44),
    "Warangal, TS": (17.97, 79.59),
    "Nashik, MH": (19.99, 73.79),
    "Ludhiana, PB": (30.90, 75.85),
    "Thanjavur, TN": (10.79, 79.14),
    "Indore, MP": (22.72, 75.86),
    "Mandya, KA": (12.52, 76.90),
    "Bardhaman, WB": (23.23, 87.86),
}

# crop: (ideal min temp °C, ideal max temp °C, min soil moisture m³/m³)
CROPS = {
    "Rice": (20, 35, 0.30),
    "Wheat": (10, 25, 0.20),
    "Maize": (18, 32, 0.20),
    "Cotton": (21, 35, 0.18),
    "Groundnut": (20, 30, 0.18),
    "Chilli": (20, 30, 0.20),
    "Sugarcane": (20, 35, 0.25),
}

# ---------------- Data ----------------
@st.cache_data(ttl=3600)
def get_weather(lat, lon, past_days):
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration",
        "hourly": "relative_humidity_2m,soil_moisture_3_to_9cm",
        "past_days": past_days, "forecast_days": 7, "timezone": "auto",
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    daily = pd.DataFrame(data["daily"])
    daily["time"] = pd.to_datetime(daily["time"])
    hourly = pd.DataFrame(data["hourly"])
    hourly["time"] = pd.to_datetime(hourly["time"])
    hourly_daily = hourly.set_index("time").resample("D").mean().reset_index()

    df = daily.merge(hourly_daily, on="time", how="left").rename(columns={
        "time": "date",
        "temperature_2m_max": "temp_max",
        "temperature_2m_min": "temp_min",
        "precipitation_sum": "rain_mm",
        "et0_fao_evapotranspiration": "et0_mm",
        "relative_humidity_2m": "humidity",
        "soil_moisture_3_to_9cm": "soil_moisture",
    })
    today = pd.Timestamp(date.today())
    df["type"] = df["date"].apply(lambda d: "Forecast" if d > today else "Past")
    return df

# ---------------- Advice logic ----------------
def get_advice(df, crop):
    tmin, tmax, sm_min = CROPS[crop]
    today = pd.Timestamp(date.today())
    next3 = df[(df["date"] > today) & (df["date"] <= today + pd.Timedelta(days=3))]
    rain_next3 = next3["rain_mm"].sum()
    soil_now = df[df["date"] <= today]["soil_moisture"].dropna().iloc[-1]
    avg_temp = ((next3["temp_max"] + next3["temp_min"]) / 2).mean()

    if rain_next3 >= 20:
        return "WAIT", f"{rain_next3:.0f} mm of rain is expected in the next 3 days. Don't sow or water now; seeds may wash away."
    if soil_now < sm_min:
        return "WATER", f"Soil moisture is low ({soil_now:.2f}, {crop} needs at least {sm_min}) and little rain is coming. Irrigate the field."
    if tmin <= avg_temp <= tmax:
        return "SOW", f"Soil has enough moisture and temperature ({avg_temp:.0f}°C) is ideal for {crop}. Good time to sow."
    return "WAIT", f"Average temperature ({avg_temp:.0f}°C) is outside the ideal {tmin}-{tmax}°C range for {crop}. Wait for better conditions."

def mobile_chart(fig):
    fig.update_layout(
        height=330,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="top", y=-0.2, x=0),
        title_font_size=16,
        xaxis_title=None,
    )
    return fig

# ---------------- Header ----------------
st.title("🌾 Crop & Weather Dashboard")

# ---------------- Filters (on main page, easy on mobile) ----------------
filters = st.expander("🔎 Filters", expanded=True)
with filters:
    f1, f2 = st.columns(2)
    location = f1.selectbox("Location", list(LOCATIONS.keys()))
    crop = f2.selectbox("Crop", list(CROPS.keys()))
    past_days = st.slider("Past days of data", 7, 90, 30)
    show_forecast = st.toggle("Show 7-day forecast", value=True)

lat, lon = LOCATIONS[location]
try:
    df = get_weather(lat, lon, past_days)
except Exception as e:
    st.error(f"Could not load weather data: {e}")
    st.stop()

with filters:
    min_d, max_d = df["date"].min().date(), df["date"].max().date()
    date_range = st.slider("Date range", min_d, max_d, (min_d, max_d))

view = df[(df["date"].dt.date >= date_range[0]) & (df["date"].dt.date <= date_range[1])]
if not show_forecast:
    view = view[view["type"] == "Past"]

st.caption(f"{location} • Crop: {crop} • Data: Open-Meteo public weather API")

# ---------------- Advice ----------------
action, reason = get_advice(df, crop)
colors = {"SOW": "#2e7d32", "WAIT": "#f9a825", "WATER": "#1565c0"}
icons = {"SOW": "🌱", "WAIT": "⏳", "WATER": "💧"}
st.markdown(
    f"""<div class="advice-box" style="background:{colors[action]}">
    <p class="advice-title">{icons[action]} Today: {action}</p>
    <p class="advice-text">{reason}</p></div>""",
    unsafe_allow_html=True,
)

# ---------------- Key metrics (2x2 grid, fits phones) ----------------
past = df[df["type"] == "Past"]
fc = df[df["type"] == "Forecast"]
m1, m2 = st.columns(2)
m1.metric("Max temp today", f"{past['temp_max'].iloc[-1]:.1f} °C")
m2.metric("Soil moisture", f"{past['soil_moisture'].dropna().iloc[-1]:.2f}")
m3, m4 = st.columns(2)
m3.metric("Rain last 7 days", f"{past['rain_mm'].tail(7).sum():.0f} mm")
m4.metric("Rain next 7 days", f"{fc['rain_mm'].sum():.0f} mm")

# ---------------- Charts ----------------
tmin, tmax, sm_min = CROPS[crop]

temp = view.melt(id_vars="date", value_vars=["temp_max", "temp_min"], var_name="Type", value_name="°C")
fig1 = px.line(temp, x="date", y="°C", color="Type", title="🌡️ Temperature vs Ideal Range")
fig1.add_hrect(y0=tmin, y1=tmax, fillcolor="green", opacity=0.1, annotation_text=f"Ideal for {crop}")

fig2 = px.bar(view, x="date", y="rain_mm", color="type", title="🌧️ Daily Rainfall (mm)",
              color_discrete_map={"Past": "#1565c0", "Forecast": "#90caf9"})

fig3 = px.line(view, x="date", y="soil_moisture", title="🟫 Soil Moisture (3-9 cm)")
fig3.add_hline(y=sm_min, line_dash="dash", line_color="red", annotation_text=f"{crop} minimum")

wb = view.melt(id_vars="date", value_vars=["rain_mm", "et0_mm"], var_name="Type", value_name="mm")
wb["Type"] = wb["Type"].map({"rain_mm": "Rain (in)", "et0_mm": "Evaporation (out)"})
fig4 = px.bar(wb, x="date", y="mm", color="Type", barmode="group", title="⚖️ Rain vs Evaporation")

# On a laptop these show 2 per row; on a phone they stack automatically
c1, c2 = st.columns(2)
c1.plotly_chart(mobile_chart(fig1), use_container_width=True)
c2.plotly_chart(mobile_chart(fig2), use_container_width=True)
c3, c4 = st.columns(2)
c3.plotly_chart(mobile_chart(fig3), use_container_width=True)
c4.plotly_chart(mobile_chart(fig4), use_container_width=True)

# ---------------- Raw data ----------------
with st.expander("📄 View & download data"):
    st.dataframe(view, use_container_width=True)
    st.download_button("Download CSV", view.to_csv(index=False), f"{location}_weather.csv")

st.caption("Rules: Rain ≥ 20 mm in next 3 days → WAIT • Soil moisture below crop need → WATER • Temperature in ideal range → SOW • Otherwise → WAIT")
