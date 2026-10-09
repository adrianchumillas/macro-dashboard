"""
Macro Dashboard — Step 1: US Treasury yield curve (data: FRED, no API key needed)
Run:  pip install -r requirements.txt   then   streamlit run app.py
"""
import concurrent.futures as cf
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------- config ----------
TENORS = {  # label: (FRED series id, maturity in years)
    "1M": ("DGS1MO", 1 / 12), "3M": ("DGS3MO", 0.25), "6M": ("DGS6MO", 0.5),
    "1Y": ("DGS1", 1), "2Y": ("DGS2", 2), "3Y": ("DGS3", 3), "5Y": ("DGS5", 5),
    "7Y": ("DGS7", 7), "10Y": ("DGS10", 10), "20Y": ("DGS20", 20), "30Y": ("DGS30", 30),
}
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
START = "2007-01-01"
COMPARE = {"1 week ago": 7, "1 month ago": 30, "6 months ago": 182, "1 year ago": 365}

INK, TEAL, RED, GREY = "#13233A", "#0E6F7A", "#B23A48", "#9AA5B1"
COMPARE_COLOURS = ["#5B7FA6", "#8FA9C4", "#C2A15C", "#B9BFC7"]

st.set_page_config(page_title="Macro Dashboard", page_icon="📈", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', system-ui, sans-serif; }
    h1, h2, h3 { font-family: 'IBM Plex Serif', Georgia, serif; color: #13233A; }
    [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- data ----------
def fetch_series(label: str, sid: str) -> pd.Series:
    df = pd.read_csv(FRED_CSV.format(sid=sid, start=START))
    date_col, val_col = df.columns[0], df.columns[1]  # 'observation_date' or 'DATE'
    s = pd.to_numeric(df[val_col], errors="coerce")
    s.index = pd.to_datetime(df[date_col])
    return s.rename(label)


@st.cache_data(ttl=3600, show_spinner="Pulling yields from FRED…")
def load_yields() -> pd.DataFrame:
    with cf.ThreadPoolExecutor(max_workers=len(TENORS)) as pool:
        futures = {pool.submit(fetch_series, lbl, sid): lbl for lbl, (sid, _) in TENORS.items()}
        series = [f.result() for f in cf.as_completed(futures)]
    df = pd.concat(series, axis=1)[list(TENORS)]
    df = df.dropna(how="all")          # drop holidays
    return df.ffill()                  # carry last value over small gaps


def row_on_or_before(df: pd.DataFrame, date) -> pd.Series:
    return df.loc[:date].iloc[-1]


def add_spreads(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["2s10s"] = (df["10Y"] - df["2Y"]) * 100   # bp
    out["3m10y"] = (df["10Y"] - df["3M"]) * 100
    out["5s30s"] = (df["30Y"] - df["5Y"]) * 100
    return out


def curve_shape(latest: pd.Series) -> str:
    s210 = latest["10Y"] - latest["2Y"]
    s310 = latest["10Y"] - latest["3M"]
    if s210 < 0 and s310 < 0:
        return "Inverted"
    if s210 < 0 or s310 < 0:
        return "Partially inverted"
    if s210 < 0.25:
        return "Flat"
    return "Normal (upward sloping)"


# ---------- UI ----------
st.title("US Treasury yield curve")

try:
    yields = load_yields()
except Exception as e:  # network / FRED outage
    st.error(f"Couldn't load data from FRED ({e}). Check your connection and refresh.")
    st.stop()

spreads = add_spreads(yields)
latest_date = yields.index[-1]
latest, prev = yields.iloc[-1], yields.iloc[-2]
st.caption(f"Latest close: {latest_date:%A %d %B %Y} · Source: FRED (St. Louis Fed)")

# Headline numbers
cols = st.columns(6)
for col, t in zip(cols[:3], ["2Y", "10Y", "30Y"]):
    col.metric(f"{t} yield", f"{latest[t]:.2f}%", f"{(latest[t] - prev[t]) * 100:+.0f} bp",
               delta_color="off")
sp_now, sp_prev = spreads.iloc[-1], spreads.iloc[-2]
for col, s in zip(cols[3:5], ["2s10s", "3m10y"]):
    col.metric(f"{s} spread", f"{sp_now[s]:+.0f} bp", f"{sp_now[s] - sp_prev[s]:+.0f} bp",
               delta_color="off")
shape = curve_shape(latest)
cols[5].metric("Curve shape", shape)
if "nverted" in shape:
    st.warning("Part of the curve is inverted — historically a recession warning signal.")

# Curve chart
st.subheader("Curve today vs history")
picked = st.multiselect("Compare with", list(COMPARE), default=["1 month ago", "1 year ago"])
x = [m for _, m in TENORS.values()]
labels = list(TENORS)

fig = go.Figure()
for colour, name in zip(COMPARE_COLOURS, picked):
    d = latest_date - timedelta(days=COMPARE[name])
    row = row_on_or_before(yields, d)
    fig.add_trace(go.Scatter(x=x, y=row.values, name=f"{name} ({row.name:%d %b %Y})",
                             mode="lines+markers", line=dict(color=colour, width=2, dash="dot")))
fig.add_trace(go.Scatter(x=x, y=latest.values, name=f"Today ({latest_date:%d %b %Y})",
                         mode="lines+markers", line=dict(color=TEAL, width=4), marker=dict(size=8)))
fig.update_layout(
    xaxis=dict(title="Maturity", type="log", tickvals=x, ticktext=labels),
    yaxis=dict(title="Yield (%)", ticksuffix="%"),
    height=460, template="plotly_white", hovermode="x unified",
    legend=dict(orientation="h", y=-0.2), margin=dict(t=20),
)
st.plotly_chart(fig, use_container_width=True)

# Change table
st.subheader("Moves by maturity (bp)")
table = pd.DataFrame({"Yield %": latest.round(2)})
table["1D"] = (latest - prev) * 100
for name, days in COMPARE.items():
    table[name.replace(" ago", "")] = (latest - row_on_or_before(yields, latest_date - timedelta(days=days))) * 100
st.dataframe(
    table.T.style.format("{:+.0f}", subset=pd.IndexSlice[table.columns[1:], :])
                 .format("{:.2f}", subset=pd.IndexSlice[["Yield %"], :])
                 .background_gradient(cmap="RdBu_r", vmin=-50, vmax=50,
                                      subset=pd.IndexSlice[table.columns[1:], :]),
    use_container_width=True,
)

# History
st.subheader("History")
c1, c2 = st.columns([3, 1])
tenors_hist = c1.multiselect("Maturities", labels, default=["3M", "2Y", "10Y", "30Y"])
window = c2.selectbox("Period", ["1Y", "3Y", "5Y", "10Y", "Max"], index=2)
start = yields.index[0] if window == "Max" else latest_date - pd.DateOffset(years=int(window[:-1]))

hist = go.Figure()
for t in tenors_hist:
    hist.add_trace(go.Scatter(x=yields.loc[start:].index, y=yields.loc[start:, t], name=t))
hist.update_layout(yaxis=dict(title="Yield (%)", ticksuffix="%"), height=380,
                   template="plotly_white", hovermode="x unified", margin=dict(t=20))
st.plotly_chart(hist, use_container_width=True)

sp = go.Figure()
for s, colour in zip(["2s10s", "3m10y", "5s30s"], [INK, TEAL, GREY]):
    sp.add_trace(go.Scatter(x=spreads.loc[start:].index, y=spreads.loc[start:, s], name=s,
                            line=dict(color=colour)))
sp.add_hline(y=0, line=dict(color=RED, width=1.5, dash="dash"),
             annotation_text="Inversion line", annotation_position="bottom right")
sp.update_layout(yaxis=dict(title="Spread (bp)"), height=340, template="plotly_white",
                 hovermode="x unified", margin=dict(t=20))
st.plotly_chart(sp, use_container_width=True)

with st.expander("Download data"):
    st.download_button("Download yields CSV", yields.to_csv().encode(), "us_yields.csv", "text/csv")
