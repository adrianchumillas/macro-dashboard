"""
Macro Dashboard: rates, inflation, jobs, markets, central bank calendar, and a daily briefing.
Data: FRED (no key needed). Optional AI briefing: add ANTHROPIC_API_KEY in Streamlit secrets.
Run locally:  pip install -r requirements.txt   then   streamlit run app.py
"""
import concurrent.futures as cf
import html
import io
import json
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# =====================================================================
# CONFIG
# =====================================================================
START = "2015-01-01"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"

TENORS = {  # label: (FRED id, maturity in years)
    "1M": ("DGS1MO", 1 / 12), "3M": ("DGS3MO", 0.25), "6M": ("DGS6MO", 0.5),
    "1Y": ("DGS1", 1), "2Y": ("DGS2", 2), "3Y": ("DGS3", 3), "5Y": ("DGS5", 5),
    "7Y": ("DGS7", 7), "10Y": ("DGS10", 10), "20Y": ("DGS20", 20), "30Y": ("DGS30", 30),
}
SERIES = {  # key: FRED id
    # policy rates
    "fed_funds": "DFF", "fed_upper": "DFEDTARU", "ecb_depo": "ECBDFR", "sonia": "IUDSOIA",
    # inflation
    "cpi": "CPIAUCSL", "core_cpi": "CPILFESL", "core_pce": "PCEPILFE",
    "breakeven10": "T10YIE", "real10": "DFII10",
    # jobs and growth
    "unemployment": "UNRATE", "payrolls": "PAYEMS", "sentiment": "UMCSENT",
    # markets
    "sp500": "SP500", "nasdaq": "NASDAQCOM", "vix": "VIXCLS",
    "hy_spread": "BAMLH0A0HYM2", "ig_spread": "BAMLC0A0CM",
    "dollar": "DTWEXBGS", "gbpusd": "DEXUSUK", "eurusd": "DEXUSEU", "usdjpy": "DEXJPUS",
    "wti": "DCOILWTICO", "brent": "DCOILBRENTEU",
    # global 10Y (monthly)
    "uk10": "IRLTLT01GBM156N", "de10": "IRLTLT01DEM156N",
}

LON, NY, FRA = ZoneInfo("Europe/London"), ZoneInfo("America/New_York"), ZoneInfo("Europe/Berlin")
WHY = {
    "Fed": "Sets the US policy rate. Moves every asset class.",
    "ECB": "Drives the euro, Bund yields and European banks.",
    "BoE": "Drives sterling, gilts and UK mortgage rates.",
    "CPI": "Biggest single driver of rate expectations.",
    "Jobs": "Payrolls, unemployment and wages: growth and the Fed path.",
    "PPI": "Pipeline inflation pressure for businesses.",
}
FLAG = {"Fed": "🇺🇸", "ECB": "🇪🇺", "BoE": "🇬🇧", "BLS": "🇺🇸"}
# Saved dates (UK time), only used if the live official calendar can't be reached.
FALLBACK = [
    ("BLS", "2026-10-14 13:30", "US CPI (September)", "CPI"),
    ("Fed", "2026-10-28 18:00", "Fed rate decision · press conference 18:30", "Fed"),
    ("ECB", "2026-10-29 13:15", "ECB rate decision · press conference 13:45", "ECB"),
    ("BoE", "2026-11-05 12:00", "BoE rate decision + Monetary Policy Report · press conference 12:30", "BoE"),
    ("BLS", "2026-11-06 13:30", "US jobs report (October)", "Jobs"),
    ("BLS", "2026-11-10 13:30", "US CPI (October)", "CPI"),
    ("BLS", "2026-12-04 13:30", "US jobs report (November)", "Jobs"),
    ("Fed", "2026-12-09 19:00", "Fed rate decision + dot plot · press conference 19:30", "Fed"),
    ("BLS", "2026-12-10 13:30", "US CPI (November)", "CPI"),
    ("BoE", "2026-12-17 12:00", "BoE rate decision", "BoE"),
    ("ECB", "2026-12-17 13:15", "ECB rate decision + staff projections · press conference 13:45", "ECB"),
    ("Fed", "2027-01-27 19:00", "Fed rate decision (tentative date)", "Fed"),
    ("BoE", "2027-02-04 12:00", "BoE rate decision + Monetary Policy Report", "BoE"),
    ("ECB", "2027-02-04 13:15", "ECB rate decision", "ECB"),
    ("Fed", "2027-03-17 18:00", "Fed rate decision + dot plot (tentative date)", "Fed"),
    ("BoE", "2027-03-18 12:00", "BoE rate decision", "BoE"),
    ("ECB", "2027-03-18 13:15", "ECB rate decision + staff projections", "ECB"),
]

TEAL, INK, RED, GREEN, AMBER, GREY = "#0E6F7A", "#13233A", "#B23A48", "#2E7D4F", "#C28A2C", "#9AA5B1"
TONE = {"risk-on": ("🟢", GREEN), "neutral": ("🟡", AMBER), "risk-off": ("🔴", RED)}

st.set_page_config(page_title="Macro Dashboard", page_icon="📈", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', system-ui, sans-serif; }
    h1, h2, h3 { font-family: 'IBM Plex Serif', Georgia, serif; color: #13233A; }
    [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-size: 1.6rem; }
    .signal { padding: .55rem .8rem; border-left: 4px solid; margin-bottom: .45rem; background: rgba(19,35,58,.03); }
    .signal b { color: #13233A; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =====================================================================
# DATA
# =====================================================================
FRED_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
                              "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Accept": "text/csv,text/plain,*/*"}


def _parse_fred(text: str) -> pd.Series | None:
    df = pd.read_csv(io.StringIO(text))
    if df.shape[1] < 2:
        return None
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    s = s[s.index.notna()].dropna().sort_index()
    return s if len(s) else None


def fetch_batch(sids: list[str]) -> dict:
    """Several FRED series in one request (much less likely to be rate-limited)."""
    url = FRED_CSV.format(sid=",".join(sids), start=START)
    r = requests.get(url, timeout=(6, 30), headers=FRED_HEADERS)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    idx = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    out = {}
    for col in df.columns[1:]:
        s = pd.to_numeric(df[col], errors="coerce")
        s.index = idx
        s = s[s.index.notna()].dropna().sort_index()
        if len(s):
            out[col] = s
    return out


def fetch(sid: str) -> tuple[pd.Series | None, str]:
    """One FRED series, two quick attempts with different methods."""
    url = FRED_CSV.format(sid=sid, start=START)
    err = ""
    for attempt in range(2):
        try:
            if attempt == 0:
                r = requests.get(url, timeout=(5, 15), headers=FRED_HEADERS)
                r.raise_for_status()
                s = _parse_fred(r.text)
            else:
                s = _parse_fred(requests.get(url, timeout=(5, 15)).text)
            if s is not None:
                return s, ""
            err = "empty response"
        except Exception as e:
            err = str(e)[:120]
        time.sleep(2)
    return None, err


# ---------- backup sources, used when FRED can't be reached ----------
TREASURY_CSV = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                "daily-treasury-rates.csv/{y}/all?type={t}&field_tdr_date_value={y}&page&_format=csv")
TREASURY_COLS = {"1 mo": "1M", "3 mo": "3M", "6 mo": "6M", "1 yr": "1Y", "2 yr": "2Y", "3 yr": "3Y",
                 "5 yr": "5Y", "7 yr": "7Y", "10 yr": "10Y", "20 yr": "20Y", "30 yr": "30Y"}
YAHOO_BACKUP = {"sp500": "^GSPC", "nasdaq": "^IXIC", "vix": "^VIX", "dollar": "DX-Y.NYB",
                "gbpusd": "GBPUSD=X", "eurusd": "EURUSD=X", "usdjpy": "JPY=X", "wti": "CL=F", "brent": "BZ=F"}
BLS_BACKUP = {"cpi": "CUSR0000SA0", "core_cpi": "CUSR0000SA0L1E", "unemployment": "LNS14000000",
              "payrolls": "CES0000000001"}


def treasury_backup() -> dict:
    out, real = {}, []
    frames = []
    this_year = datetime.now().year
    for y in range(this_year - 4, this_year + 1):
        for kind in ["daily_treasury_yield_curve", "daily_treasury_real_yield_curve"]:
            try:
                r = requests.get(TREASURY_CSV.format(y=y, t=kind), timeout=(6, 30), headers=FRED_HEADERS)
                r.raise_for_status()
                df = pd.read_csv(io.StringIO(r.text))
                df.index = pd.to_datetime(df.iloc[:, 0], errors="coerce")
                df.columns = [str(c).strip().lower().replace("yr", "yr") for c in df.columns]
                (real if "real" in kind else frames).append(df)
            except Exception as e:
                print(f"[macro] treasury {kind} {y} failed: {e}", flush=True)
    if frames:
        df = pd.concat(frames).sort_index()
        for col, lbl in TREASURY_COLS.items():
            if col in df.columns:
                s = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(s):
                    out[lbl] = s[~s.index.duplicated()]
    if real:
        df = pd.concat(real).sort_index()
        if "10 yr" in df.columns:
            s = pd.to_numeric(df["10 yr"], errors="coerce").dropna()
            out["real10"] = s[~s.index.duplicated()]
            if "10Y" in out:
                out["breakeven10"] = (out["10Y"] - out["real10"]).dropna()
    return out


def nyfed_backup() -> dict:
    out = {}
    try:
        url = ("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?"
               f"startDate={START}&endDate={datetime.now():%Y-%m-%d}")
        rows = requests.get(url, timeout=(6, 30), headers=FRED_HEADERS).json()["refRates"]
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(df["effectiveDate"])
        df = df.sort_index()
        out["fed_funds"] = pd.to_numeric(df["percentRate"], errors="coerce").dropna()
        if "targetRateTo" in df:
            out["fed_upper"] = pd.to_numeric(df["targetRateTo"], errors="coerce").dropna()
    except Exception as e:
        print(f"[macro] NY Fed failed: {e}", flush=True)
    return out


def ecb_rate_backup() -> dict:
    try:
        url = "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?format=csvdata&startPeriod=" + START
        df = pd.read_csv(io.StringIO(requests.get(url, timeout=(6, 30), headers=FRED_HEADERS).text))
        s = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
        s.index = pd.to_datetime(df["TIME_PERIOD"], errors="coerce")
        return {"ecb_depo": s.dropna().sort_index()}
    except Exception as e:
        print(f"[macro] ECB rate failed: {e}", flush=True)
        return {}


def yahoo_backup() -> dict:
    try:
        import yfinance as yf
        df = yf.download(list(YAHOO_BACKUP.values()), start=START, progress=False, auto_adjust=False, threads=True)
        close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]]
        out = {}
        for key, t in YAHOO_BACKUP.items():
            if t in close.columns:
                s = pd.to_numeric(close[t], errors="coerce").dropna()
                s.index = pd.to_datetime(s.index).tz_localize(None)
                if len(s):
                    out[key] = s
        return out
    except Exception as e:
        print(f"[macro] Yahoo backup failed: {e}", flush=True)
        return {}


def bls_backup() -> dict:
    out = {}
    try:
        y = datetime.now().year
        r = requests.post("https://api.bls.gov/publicAPI/v1/timeseries/data/",
                          json={"seriesid": list(BLS_BACKUP.values()), "startyear": str(y - 9), "endyear": str(y)},
                          timeout=(6, 30), headers=FRED_HEADERS)
        inv = {v: k for k, v in BLS_BACKUP.items()}
        for ser in r.json()["Results"]["series"]:
            pts = {pd.Timestamp(int(d["year"]), int(d["period"][1:]), 1): float(d["value"])
                   for d in ser["data"] if d["period"].startswith("M") and d["period"] != "M13"
                   and d["value"] not in ("-", "")}
            if pts:
                out[inv[ser["seriesID"]]] = pd.Series(pts).sort_index()
    except Exception as e:
        print(f"[macro] BLS failed: {e}", flush=True)
    return out


@st.cache_data(ttl=3600, show_spinner="Pulling the latest data (first load can take a minute)…")
def load_all() -> tuple[dict, dict, str]:
    t0 = time.time()
    ids = {**{t: sid for t, (sid, _) in TENORS.items()}, **SERIES}
    sids = list(dict.fromkeys(ids.values()))
    by_sid = {}

    # 1. Quick probe: is FRED reachable from this server at all?
    probe, perr = fetch("DGS10")
    fred_ok = probe is not None
    print(f"[macro] FRED probe: {'ok' if fred_ok else 'failed: ' + perr} ({time.time() - t0:.0f}s)", flush=True)
    if fred_ok:
        by_sid["DGS10"] = probe
        rest = [s for s in sids if s != "DGS10"]
        groups = [rest[i:i + 6] for i in range(0, len(rest), 6)]
        with cf.ThreadPoolExecutor(max_workers=3) as pool:
            for fut in [pool.submit(fetch_batch, g) for g in groups]:
                try:
                    by_sid.update(fut.result())
                except Exception as e:
                    print(f"[macro] batch failed: {str(e)[:150]}", flush=True)
        todo = [s for s in sids if s not in by_sid]
        if todo:
            with cf.ThreadPoolExecutor(max_workers=4) as pool:
                for sid, (s, err) in zip(todo, pool.map(fetch, todo)):
                    if s is not None:
                        by_sid[sid] = s
    data = {k: by_sid[sid] for k, sid in ids.items() if sid in by_sid}

    # 2. Backups for anything still missing
    source = "FRED"
    need = [k for k in ids if k not in data]
    if need:
        backups = []
        if any(t in need for t in TENORS) or "real10" in need or "breakeven10" in need:
            backups.append(treasury_backup)
        if "fed_funds" in need or "fed_upper" in need:
            backups.append(nyfed_backup)
        if "ecb_depo" in need:
            backups.append(ecb_rate_backup)
        if any(k in need for k in YAHOO_BACKUP):
            backups.append(yahoo_backup)
        if any(k in need for k in BLS_BACKUP):
            backups.append(bls_backup)
        with cf.ThreadPoolExecutor(max_workers=5) as pool:
            for res in pool.map(lambda f: f(), backups):
                for k, s in res.items():
                    if k in need and k not in data:
                        data[k] = s
        if not fred_ok:
            source = "backup sources (FRED unreachable)"
    errors = {k: "unavailable" for k in ids if k not in data}
    print(f"[macro] loaded {len(data)}/{len(ids)} series via {source} in {time.time() - t0:.0f}s", flush=True)
    if not all(t in data for t in TENORS):
        raise RuntimeError(f"Treasury yields unavailable from FRED and Treasury.gov ({perr})")
    return data, errors, source


try:
    D, load_errors, DATA_SOURCE = load_all()
except Exception as e:
    st.error("Couldn't load market data right now. Refresh in a minute to try again.")
    st.caption(f"Details: {e}")
    st.stop()
missing = list(load_errors)

yields = pd.concat([D[t].rename(t) for t in TENORS], axis=1).dropna(how="all").ffill()


# ---------- helpers ----------
def has(*keys):
    return all(k in D for k in keys)


def last(key):
    s = D[key]
    return s.iloc[-1]


def value_ago(s: pd.Series, days: int):
    sub = s.loc[: s.index[-1] - timedelta(days=days)]
    return sub.iloc[-1] if len(sub) else None


def change(key, days, pct=False):
    s = D[key]
    old = value_ago(s, days)
    if old is None:
        return None
    return (s.iloc[-1] / old - 1) * 100 if pct else s.iloc[-1] - old


def yoy(key):
    return (D[key].pct_change(12) * 100).dropna()


def fmt(x, nd=2, suffix=""):
    return "n/a" if x is None or pd.isna(x) else f"{x:,.{nd}f}{suffix}"


def line_chart(series: dict, title="", yfmt="", zero=False, start=None, height=320):
    fig = go.Figure()
    colours = [TEAL, INK, AMBER, GREY, RED, GREEN]
    for (name, s), c in zip(series.items(), colours):
        if s is None:
            continue
        s = s.loc[start:] if start is not None else s
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, line=dict(color=c, width=2)))
    if zero:
        fig.add_hline(y=0, line=dict(color=RED, width=1, dash="dash"))
    fig.update_layout(title=title, height=height, template="plotly_white", hovermode="x unified",
                      margin=dict(t=40 if title else 10, b=10), yaxis=dict(ticksuffix=yfmt),
                      legend=dict(orientation="h", y=-0.15))
    return fig


# =====================================================================
# LIVE CALENDAR: pulled from official sources, refreshed every 12 hours
# =====================================================================
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                       "August", "September", "October", "November", "December"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
                         "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
           "Accept": "text/html,application/xhtml+xml,text/calendar;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-GB,en;q=0.9"}


def now_uk():
    return datetime.now(LON)


def get_page(url):
    r = requests.get(url, headers=BROWSER, timeout=20)
    r.raise_for_status()
    return r.text


def page_text(url):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", get_page(url))
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))


def make_event(src, dt, name, kind):
    return dict(src=src, dt=dt.astimezone(LON), flag=FLAG[src], name=name, why=WHY[kind])


def scrape_fed():
    t = page_text("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    parts = re.split(r"(20\d\d) FOMC Meetings", t)
    out, seen, this_year = [], set(), now_uk().year
    for i in range(1, len(parts), 2):
        year = int(parts[i])
        if year < this_year:
            continue
        pat = rf"\b((?:{MONTH_RE})(?:/(?:{MONTH_RE}))?)\s+(\d{{1,2}})-(\d{{1,2}})(\*?)"
        for mon, _, d2, star in re.findall(pat, parts[i + 1]):
            m = MONTHS[mon.split("/")[-1]]
            dt = datetime(year, m, int(d2), 14, 0, tzinfo=NY)
            if dt in seen:
                continue
            seen.add(dt)
            press = (dt + timedelta(minutes=30)).astimezone(LON)
            name = "Fed rate decision" + (" + dot plot" if star else "") + f" · press conference {press:%H:%M}"
            if year > this_year:
                name += " (tentative date)"
            out.append(make_event("Fed", dt, name, "Fed"))
    return out


def scrape_ecb():
    t = page_text("https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html")
    out, seen = [], set()
    for m in re.finditer(r"(\d{2})/(\d{2})/(\d{4})((?:(?!\d{2}/\d{2}/\d{4}).){0,300})", t):
        body = m.group(4).lower()
        if "monetary policy meeting" not in body or "non-monetary" in body:
            continue
        if "day 2" not in body and "press conference" not in body:
            continue
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dt = datetime(y, mo, d, 14, 15, tzinfo=FRA)
        if dt in seen:
            continue
        seen.add(dt)
        press = (dt + timedelta(minutes=30)).astimezone(LON)
        extra = " + staff projections" if mo in (3, 6, 9, 12) else ""
        out.append(make_event("ECB", dt, f"ECB rate decision{extra} · press conference {press:%H:%M}", "ECB"))
    return out


def scrape_boe():
    t = page_text("https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates")
    matches = list(re.finditer(rf"(Thursday)\s+(\d{{1,2}})\s+({MONTH_RE})\b", t))
    out, seen, today = [], set(), now_uk().date()
    for i, m in enumerate(matches):
        context = t[m.end(): matches[i + 1].start() if i + 1 < len(matches) else m.end() + 200][:200]
        if not re.search(r"MPC|Monetary Policy|Bank Rate", context):
            continue
        day, mon = int(m.group(2)), MONTHS[m.group(3)]
        # The stated weekday pins down the year (unique within a 4-year window)
        for y in range(today.year - 1, today.year + 3):
            try:
                d = date(y, mon, day)
            except ValueError:
                continue
            if d.weekday() == 3:
                break
        else:
            continue
        if d in seen:
            continue
        seen.add(d)
        mpr = "Monetary Policy Report" in context
        name = "BoE rate decision" + (" + Monetary Policy Report · press conference 12:30" if mpr else "")
        out.append(make_event("BoE", datetime(d.year, d.month, d.day, 12, 0, tzinfo=LON), name, "BoE"))
    return out


def scrape_bls():
    txt = get_page("https://www.bls.gov/schedule/news_release/bls.ics")
    txt = txt.replace("\r\n ", "").replace("\n ", "")
    labels = {"Employment Situation": ("US jobs report", "Jobs"), "Consumer Price Index": ("US CPI", "CPI"),
              "Producer Price Index": ("US PPI", "PPI")}
    out = []
    for block in txt.split("BEGIN:VEVENT")[1:]:
        s = re.search(r"SUMMARY[^:]*:(.+)", block)
        d = re.search(r"DTSTART([^:\r\n]*):(\d{8})(?:T(\d{4,6}))?(Z?)", block)
        if not (s and d):
            continue
        m = re.match(r"\s*(Employment Situation|Consumer Price Index|Producer Price Index) for (\w+ \d{4})", s.group(1))
        if not m:
            continue
        ymd, hm, z = d.group(2), d.group(3) or "083000", d.group(4)
        dt = datetime(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]), int(hm[:2]), int(hm[2:4]),
                      tzinfo=ZoneInfo("UTC") if z else NY)
        label, kind = labels[m.group(1)]
        out.append(make_event("BLS", dt, f"{label} ({m.group(2).split()[0]})", kind))
    return out


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def load_calendar():
    cutoff = now_uk() - timedelta(days=1)
    events, status = [], {}
    sources = [("Fed", scrape_fed, "federalreserve.gov"), ("ECB", scrape_ecb, "ecb.europa.eu"),
               ("BoE", scrape_boe, "bankofengland.co.uk"), ("BLS", scrape_bls, "bls.gov")]
    for src, fn, site in sources:
        try:
            got = [e for e in fn() if e["dt"] >= cutoff]
            if len(got) < 2:
                raise ValueError("couldn't read enough dates")
            events += got
            status[src] = (True, f"Live from {site} ({len(got)} upcoming)")
        except Exception as ex:
            for s, when, name, kind in FALLBACK:
                if s == src:
                    dt = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=LON)
                    events.append(make_event(s, dt, name, kind))
            status[src] = (False, f"Using saved dates ({type(ex).__name__})")
    events.sort(key=lambda e: e["dt"])
    return events, status, now_uk()


def data_status():
    rows = []
    today = pd.Timestamp(now_uk().date())
    for k, s in D.items():
        monthly = s.index.to_series().diff().median() > pd.Timedelta(days=20)
        age = (today - s.index[-1]).days
        limit = 100 if monthly else 7
        rows.append(dict(Series=k, Frequency="Monthly" if monthly else "Daily",
                         **{"Latest data": f"{s.index[-1]:%d %b %Y}", "Status": "✅" if age <= limit else "⚠️ Stale"}))
    return pd.DataFrame(rows)


# =====================================================================
# SIGNALS: rule-based read of the data
# =====================================================================
def build_signals():
    sig = []

    def add(area, reading, tone, why):
        sig.append(dict(area=area, reading=reading, tone=tone, why=why))

    # 1. Yield curve
    y = yields
    s210 = (y["10Y"] - y["2Y"]) * 100
    d210 = s210.iloc[-1] - value_ago(s210, 30)
    d2 = (y["2Y"].iloc[-1] - value_ago(y["2Y"], 30)) * 100
    d10 = (y["10Y"].iloc[-1] - value_ago(y["10Y"], 30)) * 100
    if s210.iloc[-1] < 0:
        add("Yield curve", f"Inverted: 2s10s at {s210.iloc[-1]:+.0f} bp", "risk-off",
            "An inverted curve has preceded most US recessions, usually by 6–18 months.")
    elif d210 > 15 and d2 < d10 and d10 > 0:
        add("Yield curve", f"Bear steepening: 2s10s {d210:+.0f} bp in a month, 10Y {d10:+.0f} bp", "risk-off",
            "Long yields rising faster points to inflation or fiscal worries. Bad for growth stocks and long bonds.")
    elif d210 > 15:
        add("Yield curve", f"Bull steepening: 2s10s {d210:+.0f} bp in a month, 2Y {d2:+.0f} bp", "neutral",
            "Short yields falling means markets expect rate cuts. Often good for bonds, mixed for stocks (growth worries).")
    elif d210 < -15:
        add("Yield curve", f"Flattening: 2s10s {d210:+.0f} bp in a month", "neutral",
            "Markets pricing tighter policy or slower growth ahead.")
    else:
        add("Yield curve", f"Normal, stable: 2s10s at {s210.iloc[-1]:+.0f} bp", "risk-on",
            "An upward-sloping, stable curve is consistent with steady growth.")

    # 2. Policy stance: real policy rate
    if has("fed_funds", "core_pce"):
        real = last("fed_funds") - yoy("core_pce").iloc[-1]
        if real > 1.5:
            add("Fed policy", f"Restrictive: real policy rate {real:+.1f}%", "risk-off",
                "Policy rate well above inflation slows the economy and supports the dollar. Room to cut if growth weakens.")
        elif real < 0:
            add("Fed policy", f"Loose: real policy rate {real:+.1f}%", "risk-on",
                "Rates below inflation support risk assets but can keep inflation sticky.")
        else:
            add("Fed policy", f"Roughly neutral: real policy rate {real:+.1f}%", "neutral",
                "Neither stimulating nor slowing the economy much.")

    # 3. Inflation momentum
    if has("core_cpi"):
        cc = D["core_cpi"]
        yoy_now = yoy("core_cpi").iloc[-1]
        ann3m = ((cc.iloc[-1] / cc.iloc[-4]) ** 4 - 1) * 100
        if ann3m > yoy_now + 0.3:
            add("Inflation", f"Re-accelerating: core CPI {ann3m:.1f}% annualised (3m) vs {yoy_now:.1f}% y/y", "risk-off",
                "Rising inflation momentum pushes back rate cuts. Negative for bonds and rate-sensitive stocks.")
        elif ann3m < yoy_now - 0.3:
            add("Inflation", f"Cooling: core CPI {ann3m:.1f}% annualised (3m) vs {yoy_now:.1f}% y/y", "risk-on",
                "Falling inflation momentum opens the door to rate cuts. Supportive for bonds and stocks.")
        else:
            add("Inflation", f"Steady: core CPI {yoy_now:.1f}% y/y", "neutral",
                "No clear change in trend. The next CPI print matters.")

    # 4. Inflation expectations
    if has("breakeven10"):
        be = last("breakeven10")
        if be > 2.6:
            add("Inflation expectations", f"Elevated: 10Y breakeven {be:.2f}%", "risk-off",
                "Markets doubt inflation returns to 2%. Pressure on long-dated bonds.")
        elif be < 2.0:
            add("Inflation expectations", f"Low: 10Y breakeven {be:.2f}%", "neutral",
                "Markets see disinflation or weak growth ahead.")
        else:
            add("Inflation expectations", f"Anchored: 10Y breakeven {be:.2f}%", "risk-on",
                "Markets trust the Fed to keep inflation near target.")

    # 5. Labour market (Sahm-style rule)
    if has("unemployment"):
        ur3 = D["unemployment"].rolling(3).mean().dropna()
        sahm = ur3.iloc[-1] - ur3.iloc[-13:-1].min()
        ur = last("unemployment")
        jobs = ""
        if has("payrolls"):
            jobs = f", payrolls {D['payrolls'].diff().iloc[-3:].mean():+.0f}k/month (3m avg)"
        if sahm >= 0.5:
            add("Jobs", f"Recession signal: unemployment {ur:.1f}% (Sahm gap {sahm:.2f}){jobs}", "risk-off",
                "The Sahm rule has flagged every US recession since 1970. Expect cuts and defensive markets.")
        elif sahm >= 0.3:
            add("Jobs", f"Softening: unemployment {ur:.1f}% (Sahm gap {sahm:.2f}){jobs}", "neutral",
                "Labour market cooling. Watch the next jobs report closely.")
        else:
            add("Jobs", f"Solid: unemployment {ur:.1f}%{jobs}", "risk-on",
                "A healthy labour market supports spending and earnings.")

    # 6. Volatility
    if has("vix"):
        v = last("vix")
        if v > 30:
            add("Volatility", f"Stress: VIX {v:.1f}", "risk-off", "Fear is high. Big daily swings, investors selling risk.")
        elif v > 20:
            add("Volatility", f"Elevated: VIX {v:.1f}", "risk-off", "Investors paying up for protection.")
        elif v < 13:
            add("Volatility", f"Very calm: VIX {v:.1f}", "neutral", "Calm markets, but complacency can precede sharp moves.")
        else:
            add("Volatility", f"Normal: VIX {v:.1f}", "risk-on", "No sign of market stress.")

    # 7. Credit
    if has("hy_spread"):
        hy = last("hy_spread")
        dhy = change("hy_spread", 30)
        widen = f", {dhy*100:+.0f} bp in a month" if dhy is not None else ""
        if hy > 5 or (dhy is not None and dhy > 0.5):
            add("Credit", f"Stress: high-yield spread {hy:.2f}%{widen}", "risk-off",
                "Lenders demanding more to fund risky companies. Often leads stocks lower.")
        elif hy < 3.5:
            add("Credit", f"Tight: high-yield spread {hy:.2f}%{widen}", "risk-on",
                "Easy financing for companies. Supportive, though little cushion if things turn.")
        else:
            add("Credit", f"Normal: high-yield spread {hy:.2f}%{widen}", "neutral", "Credit conditions unremarkable.")

    # 8. Dollar
    if has("dollar"):
        dd = change("dollar", 30, pct=True)
        if dd is not None:
            if dd > 2:
                add("US dollar", f"Strengthening: {dd:+.1f}% in a month", "risk-off",
                    "A strong dollar tightens global financial conditions. Headwind for emerging markets, commodities and US multinationals.")
            elif dd < -2:
                add("US dollar", f"Weakening: {dd:+.1f}% in a month", "risk-on",
                    "A weaker dollar eases global conditions. Tailwind for emerging markets and commodities.")
            else:
                add("US dollar", f"Stable: {dd:+.1f}% in a month", "neutral", "No major currency pressure.")

    # 9. Oil
    if has("wti"):
        do = change("wti", 30, pct=True)
        if do is not None:
            if do > 10:
                add("Oil", f"Surging: WTI {do:+.0f}% in a month to ${last('wti'):.0f}", "risk-off",
                    "Higher energy costs feed inflation and squeeze consumers. Good for energy stocks.")
            elif do < -10:
                add("Oil", f"Falling: WTI {do:+.0f}% in a month to ${last('wti'):.0f}", "neutral",
                    "Lower inflation pressure, but can signal weaker global demand.")
            else:
                add("Oil", f"Stable: WTI ${last('wti'):.0f} ({do:+.0f}% in a month)", "neutral", "Energy not a major driver right now.")

    # 10. Equities trend
    if has("sp500"):
        sp = D["sp500"]
        hi = sp.loc[sp.index[-1] - timedelta(days=365):].max()
        dd = (sp.iloc[-1] / hi - 1) * 100
        ma200 = sp.rolling(200).mean().iloc[-1]
        trend = "above" if sp.iloc[-1] > ma200 else "below"
        if dd < -10:
            add("Stocks", f"Correction: S&P 500 {dd:.1f}% from 52-week high, {trend} 200-day average", "risk-off",
                "Stocks in a correction. Risk appetite is weak.")
        elif dd > -3 and trend == "above":
            add("Stocks", f"Near highs: S&P 500 {dd:.1f}% from 52-week high, above 200-day average", "risk-on",
                "Uptrend intact. Investors are comfortable taking risk.")
        else:
            add("Stocks", f"Pullback: S&P 500 {dd:.1f}% from 52-week high, {trend} 200-day average", "neutral",
                "Mixed trend. Watch whether support holds.")
    return sig


def regime(sig):
    on = sum(s["tone"] == "risk-on" for s in sig)
    off = sum(s["tone"] == "risk-off" for s in sig)
    score = on - off
    if score >= 3:
        return "Risk-on", GREEN, on, off
    if score <= -3:
        return "Risk-off", RED, on, off
    return "Mixed", AMBER, on, off


def upcoming_events(n=None, within_days=None):
    now = now_uk()
    events, _, _ = load_calendar()
    rows = []
    for e in events:
        if e["dt"] < now - timedelta(hours=2):
            continue
        days = (e["dt"].date() - now.date()).days
        if within_days is not None and days > within_days:
            continue
        rows.append({**e, "days": days})
    return rows[:n] if n else rows


def snapshot(sig):
    """Compact data snapshot for the AI briefing."""
    snap = {"date": str(yields.index[-1].date()),
            "yields_%": {t: round(yields[t].iloc[-1], 2) for t in ["3M", "2Y", "10Y", "30Y"]},
            "yield_changes_1m_bp": {t: round((yields[t].iloc[-1] - value_ago(yields[t], 30)) * 100) for t in ["2Y", "10Y"]}}
    for k in ["fed_funds", "ecb_depo", "sonia", "breakeven10", "real10", "vix", "hy_spread", "unemployment",
              "sp500", "nasdaq", "dollar", "gbpusd", "eurusd", "usdjpy", "wti", "brent"]:
        if has(k):
            snap[k] = {"last": round(float(last(k)), 3)}
            c = change(k, 30, pct=k in ["sp500", "nasdaq", "dollar", "wti", "brent", "gbpusd", "eurusd", "usdjpy"])
            if c is not None:
                snap[k]["chg_1m"] = round(float(c), 2)
    for k in ["cpi", "core_cpi", "core_pce"]:
        if has(k):
            snap[f"{k}_yoy_%"] = round(float(yoy(k).iloc[-1]), 2)
    snap["signals"] = [f"{s['area']}: {s['reading']}" for s in sig]
    snap["market_expectations"] = [f"{nm}: {line}" for _, nm, line in market_expectation_lines()]
    try:
        snap["headlines"] = [f"{it['title']} ({it['source']})" for it in load_news()[:15]]
    except Exception:
        pass
    snap["upcoming_events_uk_time"] = [f"{e['dt']:%a %d %b %H:%M} {e['name']}" for e in upcoming_events(6)]
    return snap


@st.cache_data(ttl=6 * 3600, show_spinner="Writing today's briefing…")
def ai_briefing(snap_json: str, api_key: str) -> str:
    prompt = (
        "You are a senior macro strategist writing a morning note for investors. Using ONLY the data below, write in UK English:\n"
        "**What's happening**: 3–4 sentences on the macro picture.\n"
        "**Implications**: one short line each for Equities, Government bonds, Credit, Currencies (USD, GBP, EUR), Commodities.\n"
        "**Market pricing**: one line on what markets expect from the Fed, ECB and BoE.\n"
        "**What to watch**: the 2–3 upcoming events or headlines that matter most and what outcome would move markets.\n"
        "Be specific with numbers. No disclaimers. Max 250 words.\n\nDATA:\n" + snap_json
    )
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": "claude-sonnet-5-5", "max_tokens": 900, "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"])


def rule_based_briefing(sig) -> str:
    label, _, on, off = regime(sig)
    worst = [s for s in sig if s["tone"] == "risk-off"]
    best = [s for s in sig if s["tone"] == "risk-on"]
    lines = [f"**Overall: {label}.** {on} of {len(sig)} indicators look supportive for risk assets and {off} look negative."]
    if best:
        lines.append("**Supportive:** " + "; ".join(f"{s['area'].lower()} ({s['reading'].split(':')[0].lower()})" for s in best) + ".")
    if worst:
        lines.append("**Concerns:** " + "; ".join(f"{s['area'].lower()} ({s['reading'].split(':')[0].lower()})" for s in worst) + ".")
    exp = market_expectation_lines()
    if exp:
        lines.append("**Market pricing:** " + " ".join(f"{nm}: {line}" for _, nm, line in exp))
    ev = upcoming_events(1)
    if ev:
        e = ev[0]
        lines.append(f"**Next big event:** {e['name']} on {e['dt']:%A %d %B} at {e['dt']:%H:%M} UK time ({e['days']} days).")
    return "\n\n".join(lines)


# =====================================================================
# RATE EXPECTATIONS: what markets are pricing for the Fed, ECB and BoE
# =====================================================================
import zipfile
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FUT_CODES = "FGHJKMNQUVXZ"


def get_api_key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return None


def yf_close(tickers, period="1y"):
    """Daily closes from Yahoo Finance as {ticker: Series}. Empty dict if unavailable."""
    try:
        import yfinance as yf
        df = yf.download(list(tickers), period=period, interval="1d", progress=False,
                         auto_adjust=False, threads=True)
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = set(df.columns.get_level_values(0))
        close = df["Close"] if "Close" in lvl0 else df.xs("Close", axis=1, level=1)
    else:
        close = df[["Close"]].rename(columns={"Close": list(tickers)[0]})
    out = {}
    for t in close.columns:
        s = pd.to_numeric(close[t], errors="coerce").dropna()
        if len(s):
            s.index = pd.to_datetime(s.index).tz_localize(None)
            out[t] = s
    return out


def fed_meeting_dates():
    events, _, _ = load_calendar()
    return sorted({e["dt"].astimezone(NY).date() for e in events if e["src"] == "Fed"})


@st.cache_data(ttl=3600, show_spinner=False)
def fed_expectations():
    """Meeting-by-meeting Fed path from fed funds futures (CME FedWatch method).
    Falls back to Treasury bill yields if futures can't be loaded."""
    effr = float(last("fed_funds")) if has("fed_funds") else None
    upper = float(last("fed_upper")) if has("fed_upper") else None
    res = dict(current=effr, upper=upper, meetings=[], horizons={}, method="")
    if effr is None:
        return res
    # Horizon view from T-bills (always available from FRED)
    for lbl, col in [("1M", "1M"), ("3M", "3M"), ("6M", "6M"), ("1Y", "1Y")]:
        res["horizons"][lbl] = float(yields[col].iloc[-1])

    today = now_uk().astimezone(NY).date()
    months, tickers = [], {}
    y, m = today.year, today.month
    for _ in range(15):
        t = f"ZQ{FUT_CODES[m - 1]}{str(y)[2:]}.CBT"
        months.append((y, m))
        tickers[(y, m)] = t
        m += 1
        if m == 13:
            y, m = y + 1, 1
    closes = yf_close(tickers.values(), period="5d")
    rates = {}
    for ym, t in tickers.items():
        if t in closes:
            r = 100 - float(closes[t].iloc[-1])
            if 0 < r < 12 and abs(r - effr) < 3:
                rates[ym] = r
    if len(rates) >= 4:
        res["method"] = "Fed funds futures (CME FedWatch method)"
        meetings = [d for d in fed_meeting_dates() if d >= today]
        mtg_months = {(d.year, d.month) for d in meetings}
        pre = effr
        for d in meetings:
            ym = (d.year, d.month)
            nxt = (d.year + (d.month == 12), d.month % 12 + 1)
            n_days = (date(nxt[0], nxt[1], 1) - timedelta(days=1)).day
            if nxt not in mtg_months and nxt in rates:
                post = rates[nxt]
            elif ym in rates and n_days - d.day > 0:
                frac = (n_days - d.day) / n_days
                post = (rates[ym] - pre * (1 - frac)) / frac
            else:
                break
            move = post - pre
            res["meetings"].append(dict(date=d, pre=pre, post=post, move_bp=move * 100,
                                        cum_bp=(post - effr) * 100, prob=min(abs(move) / 0.25, 1.0)))
            pre = post
    else:
        res["method"] = "Treasury bill yields (futures unavailable)"
    return res


@st.cache_data(ttl=3600, show_spinner=False)
def ecb_expectations():
    res = dict(current=None, horizons={}, method="Euro area AAA government curve (ECB)")
    try:
        url = ("https://data-api.ecb.europa.eu/service/data/YC/"
               "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M+SR_6M+SR_1Y+SR_2Y?format=csvdata&lastNObservations=5")
        df = pd.read_csv(io.StringIO(requests.get(url, timeout=20, headers=BROWSER).text))
        key_col = "DATA_TYPE_FM" if "DATA_TYPE_FM" in df.columns else None
        for code, lbl in [("SR_3M", "3M"), ("SR_6M", "6M"), ("SR_1Y", "1Y"), ("SR_2Y", "2Y")]:
            sub = df[df[key_col] == code] if key_col else df[df["KEY"].str.endswith(code)]
            sub = sub.sort_values("TIME_PERIOD")
            if len(sub):
                res["horizons"][lbl] = float(sub["OBS_VALUE"].iloc[-1])
    except Exception as e:
        res["error"] = type(e).__name__
    try:
        url = "https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?format=csvdata&lastNObservations=3"
        df = pd.read_csv(io.StringIO(requests.get(url, timeout=20, headers=BROWSER).text))
        res["current"] = float(df.sort_values("TIME_PERIOD")["OBS_VALUE"].iloc[-1])
        res["current_label"] = "€STR"
    except Exception:
        if has("ecb_depo"):
            res["current"] = float(last("ecb_depo")) - 0.10
            res["current_label"] = "€STR (est.)"
    res["policy"] = float(last("ecb_depo")) if has("ecb_depo") else None
    return res


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def boe_expectations():
    res = dict(current=float(last("sonia")) if has("sonia") else None, current_label="SONIA",
               horizons={}, method="SONIA OIS curve (Bank of England)")
    try:
        r = requests.get("https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/"
                         "latest-yield-curve-data.zip", headers=BROWSER, timeout=30)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        name = next(n for n in z.namelist() if "ois" in n.lower() and "daily" in n.lower())
        xl = pd.ExcelFile(io.BytesIO(z.read(name)))
        sheets = [s for s in xl.sheet_names if "spot" in s.lower()]
        sheet = next((s for s in sheets if "short" in s.lower()), sheets[0])
        df = xl.parse(sheet, header=None)
        hdr = next(i for i in range(min(15, len(df)))
                   if pd.to_numeric(df.iloc[i, 1:], errors="coerce").notna().sum() >= 8)
        mats = pd.to_numeric(df.iloc[hdr, 1:], errors="coerce")
        data = df.iloc[hdr + 1:]
        data = data[pd.to_datetime(data.iloc[:, 0], errors="coerce").notna()]
        row = data[pd.to_numeric(data.iloc[:, 1:].stack(), errors="coerce").groupby(level=0).count() >= 5].iloc[-1]
        vals = pd.to_numeric(row.iloc[1:], errors="coerce")
        in_months = mats.max() <= 60 and mats.min() >= 1
        curve = pd.Series(vals.values, index=(mats.values if in_months else mats.values * 12)).dropna()
        for lbl, mo in [("1M", 1), ("3M", 3), ("6M", 6), ("1Y", 12), ("2Y", 24)]:
            idx = (abs(curve.index - mo)).argmin()
            if abs(curve.index[idx] - mo) <= 1.5:
                res["horizons"][lbl] = float(curve.iloc[idx])
        res["as_of"] = str(pd.to_datetime(row.iloc[0]).date())
        if res["current"] is None and "1M" in res["horizons"]:
            res["current"], res["current_label"] = res["horizons"]["1M"], "SONIA (1M OIS)"
    except Exception as e:
        res["error"] = type(e).__name__
    return res


def describe_path(current, horizons, step=0.25):
    """Plain-English read of a horizon curve vs the current overnight rate."""
    if current is None or "1Y" not in horizons:
        return None
    chg = (horizons["1Y"] - current) * 100
    n = abs(chg) / (step * 100)
    if abs(chg) < 10:
        return "Markets expect rates to stay roughly where they are over the next year."
    word = "cuts" if chg < 0 else "hikes"
    return f"Markets price about {n:.1f} quarter-point {word} over the next 12 months ({chg:+.0f} bp)."


def fed_next_meeting_text(fx):
    if not fx["meetings"]:
        return None
    m = fx["meetings"][0]
    mv = m["move_bp"]
    if abs(mv) < 5:
        return f"Hold expected at the {m['date']:%d %b} meeting (~{100 - m['prob'] * 100:.0f}% probability)."
    word = "cut" if mv < 0 else "hike"
    if abs(mv) > 30:
        return f"{abs(mv):.0f} bp of {word}s priced for the {m['date']:%d %b} meeting."
    return f"{m['prob'] * 100:.0f}% probability of a 25 bp {word} on {m['date']:%d %b}."


def fed_path_text(fx):
    """12-month view: from futures if available, otherwise from T-bills."""
    if fx["meetings"]:
        horizon = date.today() + timedelta(days=365)
        within = [m for m in fx["meetings"] if m["date"] <= horizon]
        if within:
            chg = within[-1]["cum_bp"]
            if abs(chg) < 10:
                return f"No net change priced through {within[-1]['date']:%b %Y}."
            word = "cuts" if chg < 0 else "hikes"
            return (f"About {abs(chg) / 25:.1f} quarter-point {word} priced by {within[-1]['date']:%b %Y} "
                    f"({chg:+.0f} bp).")
    return describe_path(fx["current"], fx["horizons"])


# =====================================================================
# COMMODITIES
# =====================================================================
COMMODITIES = {  # name: (Yahoo ticker, unit, FRED fallback key, drivers)
    "Gold": ("GC=F", "$/oz", None, "Falls when real yields and the dollar rise; rallies on fear, geopolitics and central bank buying."),
    "Silver": ("SI=F", "$/oz", None, "Half precious metal, half industrial (solar panels, electronics). More volatile than gold."),
    "Copper": ("HG=F", "$/lb", None, "Barometer of global growth, especially Chinese construction and manufacturing, plus grid and EV demand."),
    "WTI crude": ("CL=F", "$/bbl", "wti", "OPEC+ supply decisions, global demand, US inventories and Middle East risk."),
    "Brent crude": ("BZ=F", "$/bbl", "brent", "Global oil benchmark. Moves with OPEC+, Russia sanctions and shipping disruption."),
    "Natural gas": ("NG=F", "$/MMBtu", None, "Weather, US storage levels and LNG exports to Europe and Asia."),
    "Wheat": ("ZW=F", "¢/bu", None, "Harvest weather, Black Sea exports and the dollar."),
    "Corn": ("ZC=F", "¢/bu", None, "US harvest, ethanol demand, weather and Chinese buying."),
}


@st.cache_data(ttl=3600, show_spinner=False)
def load_commodities():
    tick = {v[0]: k for k, v in COMMODITIES.items()}
    got = yf_close(tick.keys(), period="5y")
    out, src = {}, {}
    for t, name in tick.items():
        if t in got:
            out[name], src[name] = got[t], "Yahoo Finance"
        elif COMMODITIES[name][2] and has(COMMODITIES[name][2]):
            out[name], src[name] = D[COMMODITIES[name][2]], "FRED"
    return out, src


def pct_change_days(s, days):
    old = value_ago(s, days)
    return None if old is None or old == 0 else (s.iloc[-1] / old - 1) * 100


def macro_read(name):
    """How current macro data tilts each commodity."""
    notes = []
    real = change("real10", 30) if has("real10") else None
    usd = change("dollar", 30, pct=True) if has("dollar") else None
    if name in ("Gold", "Silver"):
        if real is not None:
            notes.append(("Real yields " + ("up" if real > 0 else "down") + f" {real * 100:+.0f} bp in a month",
                          -1 if real > 0.05 else 1 if real < -0.05 else 0))
        if usd is not None:
            notes.append((f"Dollar {usd:+.1f}% in a month", -1 if usd > 1 else 1 if usd < -1 else 0))
        if has("vix") and last("vix") > 20:
            notes.append((f"VIX at {last('vix'):.0f}: safe-haven demand", 1))
    if name in ("WTI crude", "Brent crude", "Copper"):
        if usd is not None:
            notes.append((f"Dollar {usd:+.1f}% in a month", -1 if usd > 1 else 1 if usd < -1 else 0))
        if has("sp500"):
            spc = change("sp500", 30, pct=True)
            if spc is not None:
                notes.append((f"Stocks {spc:+.1f}% in a month (growth sentiment)", 1 if spc > 2 else -1 if spc < -2 else 0))
    if name in ("Wheat", "Corn") and usd is not None:
        notes.append((f"Dollar {usd:+.1f}% in a month", -1 if usd > 1 else 1 if usd < -1 else 0))
    return notes


# =====================================================================
# NEWS: headlines, and which markets they move
# =====================================================================
NEWS_QUERIES = ["Federal Reserve interest rates", "Bank of England interest rates", "European Central Bank rates",
                "inflation CPI", "jobs report unemployment", "treasury yields bonds", "stock market",
                "oil prices OPEC", "gold price", "copper price", "natural gas prices", "tariffs trade",
                "geopolitical tensions markets", "Nvidia earnings AI stocks", "pound sterling", "wheat corn prices"]

UP = r"\b(surg\w*|soar\w*|jump\w*|rall(y|ies|ied)|ris(e|es|ing)|rose|climb\w*|gain\w*|record high|spik\w*|higher|rebound\w*|boost\w*)\b"
DOWN = r"\b(fall\w*|fell|drop\w*|slump\w*|plung\w*|tumbl\w*|sink\w*|sank|slid\w*|slip\w*|lower|declin\w*|retreat\w*|weak\w*)\b"


def _has(p, t):
    return re.search(p, t, re.I) is not None


def tone(t):
    up, down = _has(UP, t), _has(DOWN, t)
    return 1 if up and not down else -1 if down and not up else 0


def classify_headline(title):
    """Rule-based: returns list of (market, direction) where direction is +1 up, -1 down, 0 unclear."""
    t = title
    out = {}

    def put(market, d):
        out.setdefault(market, d)

    hawk = _has(r"\b(hike|hikes|hiking|hawkish|tighten\w*|higher for longer|raise rates|rate rise)\b", t)
    dove = _has(r"\b(rate cuts?|cuts? rates|cutting rates|dovish|eas(e|es|ing)|pause|lower rates)\b", t)
    policy = 1 if hawk and not dove else -1 if dove and not hawk else 0
    if _has(r"\b(Fed|Federal Reserve|FOMC|Powell|Warsh)\b", t):
        for mk, s in [("US yields", 1), ("USD", 1), ("US stocks", -1), ("Gold", -1)]:
            put(mk, s * policy)
    if _has(r"\b(Bank of England|BoE|Bailey|MPC|gilts?)\b", t):
        for mk, s in [("UK gilt yields", 1), ("GBP", 1), ("UK stocks", -1)]:
            put(mk, s * policy)
    if _has(r"\b(ECB|European Central Bank|Lagarde)\b", t):
        for mk, s in [("Euro bond yields", 1), ("EUR", 1), ("European stocks", -1)]:
            put(mk, s * policy)
    if _has(r"\b(inflation|CPI|PCE|price pressures?)\b", t):
        hot = _has(r"\b(hot\w*|accelerat\w*|higher than expected|above expectations|sticky|ris(e|es|ing)|jump\w*|surg\w*)\b", t)
        cool = _has(r"\b(cool\w*|slow\w*|eas(e|es|ing)|lower than expected|below expectations|fall\w*|fell|declin\w*)\b", t)
        d = 1 if hot and not cool else -1 if cool and not hot else 0
        for mk, s in [("US yields", 1), ("USD", 1), ("US stocks", -1)]:
            put(mk, s * d)
    if _has(r"\b(payrolls?|jobs report|jobs data|unemployment|jobless|hiring|labou?r market)\b", t):
        if _has(r"\b(unemployment|jobless)\b", t):
            d = -tone(t)
        else:
            strong = _has(r"\b(strong\w*|beat\w*|surg\w*|jump\w*|robust|adds?|added|hot)\b", t)
            weak = _has(r"\b(weak\w*|miss\w*|slow\w*|cool\w*|disappoint\w*|layoffs?|cuts? jobs)\b", t)
            d = 1 if strong and not weak else -1 if weak and not strong else 0
        for mk, s in [("US yields", 1), ("USD", 1), ("US stocks", 1)]:
            put(mk, s * d)
    if _has(r"\b(oil|crude|OPEC\+?|Brent|WTI|barrel)\b", t):
        bull = _has(r"\b(output cuts?|cuts? output|supply cuts?|disrupt\w*|sanction\w*|attack\w*|blockade|shortage)\b", t)
        bear = _has(r"\b(boost\w* output|raise\w* output|output (hike|increase)|surplus|glut|ceasefire|oversupply)\b", t)
        d = 1 if bull and not bear else -1 if bear and not bull else tone(t)
        for mk, s in [("Oil", 1), ("Energy stocks", 1), ("Airlines", -1), ("Inflation expectations", 1)]:
            put(mk, s * d)
    if _has(r"\b(natural gas|LNG|gas prices)\b", t):
        put("Natural gas", tone(t))
    if _has(r"\bgold\b", t):
        put("Gold", tone(t) or (1 if _has(r"safe.haven|record", t) else 0))
    if _has(r"\bsilver\b", t):
        put("Silver", tone(t))
    if _has(r"\b(copper|aluminium|aluminum|metals)\b", t):
        put("Copper", tone(t))
    if _has(r"\b(wheat|corn|grain|harvest|drought)\b", t):
        d = 1 if _has(r"drought|shortage|export ban", t) else tone(t)
        put("Wheat & corn", d)
    if _has(r"\b(China|Chinese|Beijing)\b", t):
        d = 1 if _has(r"stimulus|support|rebound|beat", t) else -1 if _has(r"slow\w*|weak\w*|deflation|property crisis", t) else 0
        for mk in ["Copper", "AUD", "Emerging markets"]:
            put(mk, d)
    if _has(r"\b(tariffs?|trade war|trade deal|trade talks)\b", t):
        d = 1 if _has(r"deal|truce|pause|exempt\w*|lift\w*|eas\w*", t) else -1 if _has(r"new|impos\w*|rais\w*|threat\w*|escalat\w*|hike", t) else 0
        for mk in ["US stocks", "Emerging markets", "Copper"]:
            put(mk, d)
    if _has(r"\b(war|missile|strikes? on|attack\w*|invasion|military|conflict|sanctions?|tensions?)\b", t):
        d = -1 if _has(r"ceasefire|peace|truce|de-?escalat\w*", t) else 1
        for mk, s in [("Oil", 1), ("Gold", 1), ("Defence stocks", 1), ("US stocks", -1), ("JPY", 1)]:
            put(mk, s * d)
    if _has(r"\b(Nvidia|Apple|Microsoft|Alphabet|Google|Meta|Amazon|Tesla|AI stocks|tech stocks|chipmakers?|semiconductors?)\b", t):
        d = 1 if _has(r"beat\w*|record|soar\w*|surg\w*|jump\w*|rall\w*|upgrade\w*", t) else -1 if _has(r"miss\w*|plung\w*|slump\w*|tumbl\w*|warn\w*|downgrade\w*|sell-?off", t) else tone(t)
        put("Nasdaq / tech", d)
    if _has(r"\b(stocks|shares|S&P|Dow|Nasdaq|FTSE|equities|Wall Street)\b", t) and not out:
        put("US stocks" if not _has(r"FTSE|London", t) else "UK stocks", tone(t))
    if _has(r"\b(treasur(y|ies)|bond yields?|yields)\b", t) and "US yields" not in out:
        put("US yields", tone(t))
    if _has(r"\b(pound|sterling|GBP)\b", t):
        put("GBP", tone(t))
    if _has(r"\b(dollar|USD|greenback)\b", t) and "USD" not in out:
        put("USD", tone(t))
    if _has(r"\b(default\w*|bankrupt\w*|credit crunch|bank failure|downgrade\w*|private credit)\b", t):
        for mk, s in [("Credit spreads", 1), ("Bank stocks", -1)]:
            put(mk, s)
    return list(out.items())


@st.cache_data(ttl=1800, show_spinner=False)
def load_news():
    items, seen = [], set()

    def grab(q):
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(q)}+when:2d&hl=en-GB&gl=GB&ceid=GB:en"
        try:
            root = ET.fromstring(requests.get(url, headers=BROWSER, timeout=15).content)
        except Exception:
            return []
        rows = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            src = (it.findtext("source") or "").strip()
            if src and title.endswith(" - " + src):
                title = title[: -len(src) - 3]
            try:
                pub = parsedate_to_datetime(it.findtext("pubDate")).astimezone(LON)
            except Exception:
                pub = None
            rows.append(dict(title=title, source=src, link=it.findtext("link"), published=pub, query=q))
        return rows[:12]

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for rows in pool.map(grab, NEWS_QUERIES):
            for r in rows:
                k = re.sub(r"\W+", "", r["title"].lower())[:60]
                if k in seen or not r["title"]:
                    continue
                seen.add(k)
                r["impacts"] = classify_headline(r["title"])
                items.append(r)
    items.sort(key=lambda r: r["published"] or datetime(2000, 1, 1, tzinfo=LON), reverse=True)
    return items[:80]


@st.cache_data(ttl=1800, show_spinner=False)
def ai_news_impacts(titles_json: str, api_key: str):
    """Ask Claude which markets each headline moves. Returns {index: [(market, dir, why)]}."""
    prompt = (
        "You are a cross-asset strategist. For each numbered headline, list the markets it most likely moves "
        "and the direction. Use only these market names: US yields, UK gilt yields, Euro bond yields, USD, GBP, EUR, "
        "JPY, US stocks, UK stocks, European stocks, Nasdaq / tech, Bank stocks, Energy stocks, Defence stocks, "
        "Airlines, Emerging markets, Credit spreads, Gold, Silver, Oil, Natural gas, Copper, Wheat & corn, "
        "Inflation expectations. Direction is 1 (price/yield up), -1 (down) or 0 (unclear). Skip headlines with no "
        "market relevance. Also give importance 1-3. Reply with ONLY a JSON array like "
        '[{"i":0,"importance":2,"impacts":[["Oil",1,"supply disruption"]]}].\n\nHEADLINES:\n' + titles_json
    )
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": "claude-sonnet-5-5", "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]},
        timeout=90,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    data = json.loads(re.sub(r"```json|```", "", text).strip())
    return {int(d["i"]): dict(importance=d.get("importance", 1),
                              impacts=[(a[0], int(a[1]), a[2] if len(a) > 2 else "") for a in d.get("impacts", [])])
            for d in data}


def news_with_impacts():
    items = load_news()
    key = get_api_key()
    mode = "rules"
    if key and items:
        try:
            titles = json.dumps({i: it["title"] for i, it in enumerate(items[:50])})
            ai = ai_news_impacts(titles, key)
            for i, it in enumerate(items[:50]):
                if i in ai:
                    it = items[i]
                    it["impacts"] = [(m, d) for m, d, _ in ai[i]["impacts"]]
                    it["why"] = "; ".join(w for _, _, w in ai[i]["impacts"] if w)
                    it["importance"] = ai[i]["importance"]
            mode = "ai"
        except Exception:
            pass
    return items, mode


def impact_board(items):
    """Net news direction per market."""
    rows = {}
    for it in items:
        for mk, d in it["impacts"]:
            r = rows.setdefault(mk, dict(Market=mk, Up=0, Down=0, Mentions=0))
            r["Mentions"] += 1
            r["Up"] += d > 0
            r["Down"] += d < 0
    df = pd.DataFrame(rows.values())
    if df.empty:
        return df
    df["Net"] = df["Up"] - df["Down"]
    df["News flow"] = df["Net"].apply(lambda n: "Bullish ↑" if n >= 2 else "Bearish ↓" if n <= -2 else "Mixed")
    return df.sort_values("Mentions", ascending=False)


def impact_tags(impacts):
    parts = []
    for mk, d in impacts:
        arrow, c = ("↑", GREEN) if d > 0 else ("↓", RED) if d < 0 else ("•", GREY)
        parts.append(f"<span style='border:1px solid {c};color:{c};border-radius:4px;padding:1px 6px;"
                     f"margin-right:4px;font-size:.8rem;white-space:nowrap'>{mk} {arrow}</span>")
    return "".join(parts)


def ago(dt):
    if dt is None:
        return ""
    mins = int((now_uk() - dt).total_seconds() // 60)
    return f"{mins} min ago" if mins < 60 else f"{mins // 60} h ago" if mins < 1440 else f"{mins // 1440} d ago"


COMMODITY_NEWS_KEYS = {"Gold": ["Gold"], "Silver": ["Silver"], "Copper": ["Copper"], "WTI crude": ["Oil"],
                       "Brent crude": ["Oil"], "Natural gas": ["Natural gas"], "Wheat": ["Wheat & corn"],
                       "Corn": ["Wheat & corn"]}


def market_expectation_lines():
    out = []
    try:
        fx = fed_expectations()
        line = " ".join(x for x in [fed_next_meeting_text(fx), fed_path_text(fx)] if x)
        if line:
            out.append(("🇺🇸", "Fed", line))
    except Exception:
        pass
    for flag, nm, fn in [("🇪🇺", "ECB", ecb_expectations), ("🇬🇧", "BoE", boe_expectations)]:
        try:
            x = fn()
            line = describe_path(x.get("current"), x["horizons"])
            if line:
                out.append((flag, nm, line))
        except Exception:
            pass
    return out


# =====================================================================
# UI
# =====================================================================
signals = build_signals()
label, colour, n_on, n_off = regime(signals)
latest_date = yields.index[-1]

st.title("Macro dashboard")
st.caption(f"Data to {latest_date:%A %d %B %Y} · Source: {DATA_SOURCE} · Refreshes hourly")
if DATA_SOURCE != "FRED":
    st.info("FRED isn't responding right now, so the app is using backup sources (US Treasury, NY Fed, "
            "ECB, BLS, Yahoo Finance). A few series, like credit spreads, are missing until FRED is back.")

with st.sidebar:
    st.header("Settings")
    period = st.selectbox("Chart period", ["1Y", "3Y", "5Y", "10Y"], index=1)
    start = latest_date - pd.DateOffset(years=int(period[:-1]))
    status_df = data_status()
    stale = status_df[status_df["Status"] != "✅"]["Series"].tolist()
    if stale or missing:
        st.warning("Check: " + ", ".join(stale + missing))
    else:
        st.success(f"All {len(status_df)} data series up to date")
    _, cal_status, _ = load_calendar()
    live = sum(ok for ok, _ in cal_status.values())
    st.caption(f"Calendar: {live}/{len(cal_status)} sources live")

tab_brief, tab_rates, tab_exp, tab_infl, tab_mkts, tab_cmd, tab_news, tab_cal = st.tabs(
    ["Briefing", "Rates & curves", "Rate expectations", "Inflation & jobs", "Markets", "Commodities", "News",
     "Calendar"])

# ---------------- BRIEFING ----------------
with tab_brief:
    st.markdown(f"<h2 style='color:{colour};margin-bottom:0'>Market regime: {label}</h2>", unsafe_allow_html=True)
    st.caption(f"{n_on} risk-on · {n_off} risk-off · {len(signals) - n_on - n_off} neutral signals")

    tiles = [("S&P 500", "sp500", 0, "", True), ("VIX", "vix", 1, "", False), ("US 10Y", None, 2, "%", False),
             ("Fed funds", "fed_funds", 2, "%", False), ("Dollar index", "dollar", 1, "", True), ("WTI oil", "wti", 1, "$", True)]
    cols = st.columns(len(tiles))
    for col, (name, key, nd, suf, pct) in zip(cols, tiles):
        if key is None:
            v, d = yields["10Y"].iloc[-1], (yields["10Y"].iloc[-1] - yields["10Y"].iloc[-2]) * 100
            col.metric(name, f"{v:.2f}%", f"{d:+.0f} bp 1D", delta_color="off")
        elif has(key):
            v = last(key)
            d = change(key, 30, pct=pct)
            vtxt = f"${v:,.{nd}f}" if suf == "$" else f"{v:,.{nd}f}{suf}"
            dtxt = (f"{d:+.1f}% 1M" if pct else f"{d:+.2f} 1M") if d is not None else None
            col.metric(name, vtxt, dtxt, delta_color="off")

    st.subheader("Today's briefing")
    api_key = get_api_key()
    if api_key:
        try:
            st.markdown(ai_briefing(json.dumps(snapshot(signals), default=str), api_key))
            st.caption("AI-generated from the data on this page. Not investment advice.")
        except Exception as e:
            st.info(f"AI briefing unavailable ({e}). Showing the automatic summary instead.")
            st.markdown(rule_based_briefing(signals))
    else:
        st.markdown(rule_based_briefing(signals))
        st.caption("Automatic summary. Add an Anthropic API key in the app's secrets for a written AI briefing.")

    st.subheader("What the data is saying")
    for s in signals:
        dot, c = TONE[s["tone"]]
        st.markdown(f"<div class='signal' style='border-color:{c}'>{dot} <b>{s['area']}</b>: {s['reading']}<br>"
                    f"<span style='opacity:.8'>{s['why']}</span></div>", unsafe_allow_html=True)

    st.subheader("What markets expect")
    for flag, nm, line in market_expectation_lines():
        st.markdown(f"{flag} **{nm}:** {line}")

    st.subheader("Top headlines")
    _items, _ = news_with_impacts()
    for it in [i for i in _items if i["impacts"]][:5]:
        st.markdown(f"[{html.escape(it['title'])}]({it['link']})  \n<span style='opacity:.7;font-size:.85rem'>"
                    f"{html.escape(it['source'])} · {ago(it['published'])}</span> {impact_tags(it['impacts'])}",
                    unsafe_allow_html=True)

    st.subheader("Coming up")
    for e in upcoming_events(4):
        when = "today" if e["days"] == 0 else f"in {e['days']} days"
        st.markdown(f"{e['flag']} **{e['name']}**  \n{e['dt']:%a %d %b, %H:%M} UK · {when}")

# ---------------- RATES ----------------
with tab_rates:
    latest, prev = yields.iloc[-1], yields.iloc[-2]
    c = st.columns(5)
    for col, t in zip(c[:3], ["2Y", "10Y", "30Y"]):
        col.metric(f"US {t}", f"{latest[t]:.2f}%", f"{(latest[t] - prev[t]) * 100:+.0f} bp", delta_color="off")
    s210 = (latest["10Y"] - latest["2Y"]) * 100
    s310 = (latest["10Y"] - latest["3M"]) * 100
    c[3].metric("2s10s", f"{s210:+.0f} bp")
    c[4].metric("3m10y", f"{s310:+.0f} bp")

    st.subheader("US Treasury curve")
    compare = {"1 week ago": 7, "1 month ago": 30, "6 months ago": 182, "1 year ago": 365}
    picked = st.multiselect("Compare with", list(compare), default=["1 month ago", "1 year ago"])
    x = [m for _, m in TENORS.values()]
    fig = go.Figure()
    for clr, name in zip(["#5B7FA6", "#8FA9C4", AMBER, GREY], picked):
        row = yields.loc[: latest_date - timedelta(days=compare[name])].iloc[-1]
        fig.add_trace(go.Scatter(x=x, y=row.values, name=f"{name} ({row.name:%d %b %Y})",
                                 mode="lines+markers", line=dict(color=clr, width=2, dash="dot")))
    fig.add_trace(go.Scatter(x=x, y=latest.values, name=f"Today ({latest_date:%d %b %Y})",
                             mode="lines+markers", line=dict(color=TEAL, width=4), marker=dict(size=8)))
    fig.update_layout(xaxis=dict(title="Maturity", type="log", tickvals=x, ticktext=list(TENORS)),
                      yaxis=dict(title="Yield", ticksuffix="%"), height=420, template="plotly_white",
                      hovermode="x unified", legend=dict(orientation="h", y=-0.2), margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True)

    a, b = st.columns(2)
    spreads = {"2s10s": (yields["10Y"] - yields["2Y"]) * 100, "3m10y": (yields["10Y"] - yields["3M"]) * 100}
    a.plotly_chart(line_chart(spreads, "Curve spreads (bp)", zero=True, start=start), use_container_width=True)
    policy = {"Fed funds": D.get("fed_funds"), "ECB deposit": D.get("ecb_depo"), "SONIA (≈ BoE rate)": D.get("sonia")}
    b.plotly_chart(line_chart(policy, "Central bank rates", "%", start=start), use_container_width=True)

    g = {"US 10Y": yields["10Y"].resample("ME").last(), "UK 10Y": D.get("uk10"), "Germany 10Y": D.get("de10")}
    st.plotly_chart(line_chart(g, "10-year government bond yields (monthly)", "%", start=start), use_container_width=True)

# ---------------- INFLATION & JOBS ----------------
with tab_infl:
    c = st.columns(5)
    for col, (name, key) in zip(c, [("CPI y/y", "cpi"), ("Core CPI y/y", "core_cpi"), ("Core PCE y/y", "core_pce")]):
        if has(key):
            s = yoy(key)
            col.metric(name, f"{s.iloc[-1]:.1f}%", f"{s.iloc[-1] - s.iloc[-2]:+.1f} vs prior month", delta_color="off")
    if has("breakeven10"):
        c[3].metric("10Y breakeven", f"{last('breakeven10'):.2f}%")
    if has("real10"):
        c[4].metric("10Y real yield", f"{last('real10'):.2f}%")

    st.plotly_chart(line_chart({"CPI": yoy("cpi") if has("cpi") else None,
                                "Core CPI": yoy("core_cpi") if has("core_cpi") else None,
                                "Core PCE (Fed target)": yoy("core_pce") if has("core_pce") else None},
                               "Inflation, % y/y (Fed target 2%)", "%", start=start), use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(line_chart({"10Y breakeven": D.get("breakeven10"), "10Y real yield": D.get("real10")},
                              "Market inflation expectations & real yields", "%", start=start), use_container_width=True)
    b.plotly_chart(line_chart({"Unemployment rate": D.get("unemployment")}, "US unemployment", "%", start=start),
                   use_container_width=True)
    a, b = st.columns(2)
    if has("payrolls"):
        pay = D["payrolls"].diff().loc[start:]
        f = go.Figure(go.Bar(x=pay.index, y=pay.values, marker_color=[GREEN if v >= 0 else RED for v in pay.values]))
        f.update_layout(title="Monthly job gains (thousands)", height=320, template="plotly_white", margin=dict(t=40, b=10))
        a.plotly_chart(f, use_container_width=True)
    b.plotly_chart(line_chart({"Consumer sentiment": D.get("sentiment")}, "University of Michigan consumer sentiment",
                              start=start), use_container_width=True)

# ---------------- MARKETS ----------------
with tab_mkts:
    spec = [("S&P 500", "sp500", 0, True), ("Nasdaq", "nasdaq", 0, True), ("VIX", "vix", 1, False),
            ("HY spread", "hy_spread", 2, False), ("GBP/USD", "gbpusd", 4, True), ("EUR/USD", "eurusd", 4, True),
            ("USD/JPY", "usdjpy", 2, True), ("Brent", "brent", 1, True)]
    for row in [spec[:4], spec[4:]]:
        cols = st.columns(4)
        for col, (name, key, nd, pct) in zip(cols, row):
            if has(key):
                d = change(key, 30, pct=pct)
                col.metric(name, f"{last(key):,.{nd}f}",
                           (f"{d:+.1f}% 1M" if pct else f"{d:+.2f} 1M") if d is not None else None, delta_color="off")

    a, b = st.columns(2)
    if has("sp500"):
        sp = D["sp500"]
        a.plotly_chart(line_chart({"S&P 500": sp, "200-day average": sp.rolling(200).mean()}, "S&P 500", start=start),
                       use_container_width=True)
    b.plotly_chart(line_chart({"VIX": D.get("vix")}, "VIX (fear gauge)", start=start), use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(line_chart({"High yield": D.get("hy_spread"), "Investment grade": D.get("ig_spread")},
                              "Corporate credit spreads", "%", start=start), use_container_width=True)
    b.plotly_chart(line_chart({"Broad dollar index": D.get("dollar")}, "US dollar", start=start), use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(line_chart({"GBP/USD": D.get("gbpusd"), "EUR/USD": D.get("eurusd")}, "Sterling & euro vs dollar",
                              start=start), use_container_width=True)
    b.plotly_chart(line_chart({"WTI": D.get("wti"), "Brent": D.get("brent")}, "Oil ($/barrel)", start=start),
                   use_container_width=True)

# ---------------- CALENDAR ----------------
with tab_cal:
    st.subheader("Central bank meetings & key data")
    ev = upcoming_events()
    if ev:
        nxt = ev[0]
        st.metric("Next event", nxt["name"].split(" · ")[0],
                  f"{nxt['dt']:%a %d %b, %H:%M} UK · in {nxt['days']} days", delta_color="off")
        table = pd.DataFrame([{"Date": f"{e['dt']:%a %d %b %Y}", "Time (UK)": f"{e['dt']:%H:%M}",
                               "": e["flag"], "Event": e["name"], "Why it matters": e["why"],
                               "Days away": e["days"]} for e in ev])
        st.dataframe(table, hide_index=True, use_container_width=True)
    _, cal_status, checked = load_calendar()
    st.markdown("**Calendar sources** (checked " + f"{checked:%d %b %H:%M} UK, rechecked every 12 hours)")
    for src_name, (ok, msg) in cal_status.items():
        st.markdown(f"{'✅' if ok else '⚠️'} {src_name}: {msg}")
    with st.expander("Data freshness: every series and its latest date"):
        st.dataframe(data_status(), hide_index=True, use_container_width=True)
        st.caption("Daily market data from FRED is usually one trading day behind. Monthly data appears when it's released.")

# ---------------- RATE EXPECTATIONS ----------------
with tab_exp:
    st.subheader("What markets expect central banks to do")
    st.caption("Market pricing, not forecasts. Updates hourly as futures and short-term rates move.")
    fx = fed_expectations()
    ex = ecb_expectations()
    bx = boe_expectations()
    nxt = {}
    for e in load_calendar()[0]:
        if e["dt"] >= now_uk() and e["src"] in ("Fed", "ECB", "BoE") and e["src"] not in nxt:
            nxt[e["src"]] = e

    def horizon_chart(name, current, horizons, colour):
        lbls = [h for h in ["1M", "3M", "6M", "1Y", "2Y"] if h in horizons]
        f = go.Figure()
        f.add_trace(go.Scatter(x=["Now"] + lbls, y=[current] + [horizons[h] for h in lbls], mode="lines+markers",
                               line=dict(color=colour, width=3), name="Market-implied rate"))
        f.add_hline(y=current, line=dict(color=GREY, dash="dot"), annotation_text="Today",
                    annotation_position="bottom right")
        f.update_layout(height=260, template="plotly_white", margin=dict(t=10, b=10),
                        yaxis=dict(ticksuffix="%", title="Rate"), showlegend=False)
        return f

    # ---- Fed ----
    st.markdown("### 🇺🇸 Federal Reserve")
    c = st.columns(3)
    if fx["upper"] is not None:
        c[0].metric("Target range", f"{fx['upper'] - 0.25:.2f}–{fx['upper']:.2f}%")
    if fx["current"] is not None:
        c[1].metric("Effective rate", f"{fx['current']:.2f}%")
    if "Fed" in nxt:
        c[2].metric("Next decision", f"{nxt['Fed']['dt']:%a %d %b}", f"{nxt['Fed']['dt']:%H:%M} UK", delta_color="off")
    for line in [fed_next_meeting_text(fx), fed_path_text(fx)]:
        if line:
            st.markdown(f"**{line}**")
    if fx["meetings"]:
        tbl = pd.DataFrame([{
            "Meeting": f"{m['date']:%d %b %Y}",
            "Expected rate after": f"{m['post']:.2f}%",
            "Move at meeting": f"{m['move_bp']:+.0f} bp",
            "Probability of move": "–" if abs(m["move_bp"]) < 5 else
                f"{m['prob'] * 100:.0f}% {'cut' if m['move_bp'] < 0 else 'hike'}",
            "Total vs today": f"{m['cum_bp']:+.0f} bp",
        } for m in fx["meetings"]])
        a, b = st.columns([3, 2])
        a.dataframe(tbl, hide_index=True, use_container_width=True)
        f = go.Figure(go.Scatter(x=["Today"] + [f"{m['date']:%b %y}" for m in fx["meetings"]],
                                 y=[fx["current"]] + [m["post"] for m in fx["meetings"]],
                                 mode="lines+markers", line=dict(color=TEAL, width=3, shape="hv")))
        f.update_layout(height=260, template="plotly_white", margin=dict(t=10, b=10),
                        yaxis=dict(ticksuffix="%", title="Expected effective rate"))
        b.plotly_chart(f, use_container_width=True)
    elif fx["current"] is not None:
        st.plotly_chart(horizon_chart("Fed", fx["current"], fx["horizons"], TEAL), use_container_width=True)
    st.caption(f"Method: {fx['method']}.")

    # ---- ECB ----
    st.markdown("### 🇪🇺 European Central Bank")
    c = st.columns(3)
    if ex.get("policy") is not None:
        c[0].metric("Deposit rate", f"{ex['policy']:.2f}%")
    if ex.get("current") is not None:
        c[1].metric(ex.get("current_label", "€STR"), f"{ex['current']:.2f}%")
    if "ECB" in nxt:
        c[2].metric("Next decision", f"{nxt['ECB']['dt']:%a %d %b}", f"{nxt['ECB']['dt']:%H:%M} UK", delta_color="off")
    if ex["horizons"] and ex.get("current") is not None:
        line = describe_path(ex["current"], ex["horizons"])
        if line:
            st.markdown(f"**{line}**")
        st.plotly_chart(horizon_chart("ECB", ex["current"], ex["horizons"], INK), use_container_width=True)
        st.caption(f"Method: {ex['method']}. Top-rated government bills can trade slightly below €STR, "
                   "so treat small moves as noise.")
    else:
        st.info("ECB market pricing couldn't be loaded right now. It will retry within the hour.")

    # ---- BoE ----
    st.markdown("### 🇬🇧 Bank of England")
    c = st.columns(3)
    if bx.get("current") is not None:
        c[0].metric("Bank Rate (≈ SONIA)", f"{bx['current'] + 0.03:.2f}%")
        c[1].metric("SONIA", f"{bx['current']:.2f}%")
    if "BoE" in nxt:
        c[2].metric("Next decision", f"{nxt['BoE']['dt']:%a %d %b}", f"{nxt['BoE']['dt']:%H:%M} UK", delta_color="off")
    if bx["horizons"] and bx.get("current") is not None:
        line = describe_path(bx["current"], bx["horizons"])
        if line:
            st.markdown(f"**{line}**")
        st.plotly_chart(horizon_chart("BoE", bx["current"], bx["horizons"], AMBER), use_container_width=True)
        st.caption(f"Method: {bx['method']}, curve dated {bx.get('as_of', 'n/a')}.")
    else:
        st.info("Bank of England market pricing couldn't be loaded right now. It will retry within a few hours.")

    with st.expander("How to read this"):
        st.markdown(
            "Futures and short-term interest rates reveal where traders think policy rates are heading. "
            "If the 1-year rate sits below today's overnight rate, markets expect cuts. If it sits above, "
            "they expect hikes. A 25 bp gap is roughly one quarter-point move. Probabilities near 50% mean "
            "the decision is a coin flip, so the outcome will move markets whichever way it goes.")

# ---------------- COMMODITIES ----------------
with tab_cmd:
    cmd, cmd_src = load_commodities()
    news_items, news_mode = news_with_impacts()
    if not cmd:
        st.info("Commodity prices couldn't be loaded right now. They'll retry within the hour.")
    else:
        names = [n for n in COMMODITIES if n in cmd]
        for row in [names[:4], names[4:]]:
            cols = st.columns(4)
            for col, n in zip(cols, row):
                s = cmd[n]
                d1, m1 = pct_change_days(s, 1), pct_change_days(s, 30)
                col.metric(f"{n} ({COMMODITIES[n][1]})", f"{s.iloc[-1]:,.2f}",
                           f"{d1:+.1f}% 1D · {m1:+.1f}% 1M" if d1 is not None and m1 is not None else None,
                           delta_color="off")

        # performance chart
        perf = pd.DataFrame({n: [pct_change_days(cmd[n], d) for d in (30, 90, 365)] for n in names},
                            index=["1M", "3M", "1Y"]).T
        f = go.Figure()
        for per, clr in zip(["1M", "3M", "1Y"], ["#8FA9C4", TEAL, INK]):
            f.add_trace(go.Bar(name=per, x=perf.index, y=perf[per], marker_color=clr))
        f.update_layout(barmode="group", height=320, template="plotly_white", margin=dict(t=30, b=10),
                        title="Performance (%)", yaxis=dict(ticksuffix="%"), legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(f, use_container_width=True)

        st.subheader("Drivers and news impact")
        pick = st.selectbox("Commodity", names)
        s = cmd[pick]
        a, b = st.columns([3, 2])
        a.plotly_chart(line_chart({pick: s, "50-day average": s.rolling(50).mean()},
                                  f"{pick} ({COMMODITIES[pick][1]})", start=start), use_container_width=True)
        with b:
            st.markdown(f"**What moves it:** {COMMODITIES[pick][3]}")
            notes = macro_read(pick)
            if notes:
                st.markdown("**Macro backdrop right now**")
                for txt, d in notes:
                    st.markdown(f"{'🟢' if d > 0 else '🔴' if d < 0 else '🟡'} {txt}")
            rel = [it for it in news_items if any(mk in COMMODITY_NEWS_KEYS[pick] for mk, _ in it["impacts"])]
            ups = sum(d > 0 for it in rel for mk, d in it["impacts"] if mk in COMMODITY_NEWS_KEYS[pick])
            downs = sum(d < 0 for it in rel for mk, d in it["impacts"] if mk in COMMODITY_NEWS_KEYS[pick])
            verdict = ("bullish ↑" if ups - downs >= 2 else "bearish ↓" if downs - ups >= 2 else "mixed")
            st.markdown(f"**News flow (last 48h): {verdict}** · {ups} pushing up, {downs} pushing down")
        for it in rel[:6]:
            st.markdown(f"[{it['title']}]({it['link']})  \n<span style='opacity:.7;font-size:.85rem'>"
                        f"{it['source']} · {ago(it['published'])}</span> {impact_tags(it['impacts'])}",
                        unsafe_allow_html=True)
        if not rel:
            st.caption("No recent headlines about this commodity.")
        st.caption("Prices: " + ", ".join(sorted(set(cmd_src.values()))) + ". Futures prices, front month.")

# ---------------- NEWS ----------------
with tab_news:
    news_items, news_mode = news_with_impacts()
    if not news_items:
        st.info("Headlines couldn't be loaded right now. They'll retry within 30 minutes.")
    else:
        st.subheader("Where the news is pushing markets")
        board = impact_board(news_items)
        if not board.empty:
            top = board.head(14)
            f = go.Figure()
            f.add_trace(go.Bar(y=top["Market"], x=top["Up"], name="Pushing up", orientation="h", marker_color=GREEN))
            f.add_trace(go.Bar(y=top["Market"], x=-top["Down"], name="Pushing down", orientation="h", marker_color=RED))
            f.update_layout(barmode="relative", height=420, template="plotly_white", margin=dict(t=10, b=10),
                            xaxis=dict(title="Number of headlines"), yaxis=dict(autorange="reversed"),
                            legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(f, use_container_width=True)
        st.caption("AI-tagged by market impact." if news_mode == "ai" else
                   "Tagged automatically by keywords. Add an Anthropic API key for sharper AI tagging.")

        st.subheader("Latest headlines")
        markets = sorted({mk for it in news_items for mk, _ in it["impacts"]})
        flt = st.multiselect("Show news affecting", markets, placeholder="All markets")
        shown = 0
        for it in news_items:
            if flt and not any(mk in flt for mk, _ in it["impacts"]):
                continue
            if not it["impacts"] and not flt:
                continue
            why = f"<br><span style='opacity:.75;font-size:.85rem'>{it['why']}</span>" if it.get("why") else ""
            st.markdown(f"<div class='signal' style='border-color:{TEAL}'><a href='{it['link']}' target='_blank'>"
                        f"<b>{html.escape(it['title'])}</b></a><br><span style='opacity:.7;font-size:.85rem'>"
                        f"{html.escape(it['source'])} · {ago(it['published'])}</span>{why}<br>"
                        f"{impact_tags(it['impacts'])}</div>", unsafe_allow_html=True)
            shown += 1
            if shown >= 40:
                break
        st.caption("Headlines via Google News, last 48 hours, refreshed every 30 minutes. "
                   "Arrows show the likely direction of the price (or yield) if the story holds.")
