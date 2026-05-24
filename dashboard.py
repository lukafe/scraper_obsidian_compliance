"""CertiK Crypto-Regulation Market Intelligence Dashboard.

Streamlit app reading from vault/_export/{jurisdicoes.csv, normas.csv, grafo.json}.

Run:
    streamlit run dashboard.py

Pages:
  1. Executive Summary — Opportunity Matrix (the money chart)
  2. World Map — choropleth by urgency × service intensity
  3. Deadline Timeline — Gantt
  4. By CertiK Service — service-first ranking
  5. By Jurisdiction — drilldown
  6. Methodology — confidence + data sources
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --- Constants from business_schema (vendored — avoid importing whole pipeline) ---

SERVICE_LABELS = {
    "smart_contract_audit": "Smart Contract Audit",
    "l1_chain_audit": "L1 Chain Audit",
    "penetration_testing": "Penetration Testing",
    "skyinsights_aml_kyt": "SkyInsights — AML / KYT",
    "skynet_threat_monitoring": "Skynet — Threat Monitoring",
    "proof_of_reserves": "Proof of Reserves",
    "skyshield_bug_bounty": "Skyshield — Bug Bounty",
    "performance_testing": "Performance Testing",
    "due_diligence": "Due Diligence",
    "formal_verification": "Formal Verification",
    "incident_response": "Incident Response",
    "independent_certification": "Independent Certification",
    "security_guidance": "Security Guidance",
    "regulatory_compliance_support": "Regulatory Compliance Support",
}

SERVICE_CATEGORIES = {
    "Security Auditing": [
        "smart_contract_audit", "l1_chain_audit",
        "penetration_testing", "formal_verification",
    ],
    "Compliance & Monitoring Products": [
        "skyinsights_aml_kyt", "skynet_threat_monitoring",
        "proof_of_reserves", "skyshield_bug_bounty",
        "performance_testing", "due_diligence", "incident_response",
    ],
    "Advisory & Certification": [
        "independent_certification", "security_guidance",
        "regulatory_compliance_support",
    ],
}

MATURIDADE_ORDER = {"alta": 3, "media": 2, "baixa": 1, "desconhecido": 0}

# Country code to choropleth ISO-3 (Plotly needs ISO-3).
ISO2_TO_ISO3 = {
    "BR": "BRA", "AR": "ARG", "MX": "MEX", "UY": "URY",
    "US": "USA", "CA": "CAN", "BM": "BMU",
    "DE": "DEU", "FR": "FRA", "IT": "ITA", "LT": "LTU", "GB": "GBR",
    "CH": "CHE",
    "SG": "SGP", "JP": "JPN", "HK": "HKG", "KR": "KOR",
    "IN": "IND", "AE": "ARE", "TR": "TUR",
    "ZA": "ZAF", "NG": "NGA", "SE": "SWE",
}

# CertiK red/black theme.
CERTIK_RED = "#E83C32"
CERTIK_DARK = "#1A0F0F"

st.set_page_config(
    page_title="CertiK Crypto-Reg Market Intel",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject CSS for CertiK theme.
st.markdown(
    f"""
    <style>
      .block-container {{padding-top: 1.5rem;}}
      h1, h2, h3 {{color: {CERTIK_RED};}}
      .metric-card {{
        background: #1F1212; border-left: 4px solid {CERTIK_RED};
        padding: 1rem; border-radius: 4px; margin-bottom: 0.5rem;
      }}
      .data-conf-high {{color: #4CAF50; font-weight: bold;}}
      .data-conf-med {{color: #FFB300;}}
      .data-conf-low {{color: #F44336;}}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Data loaders ---


@st.cache_data
def load_jurisdicoes() -> pd.DataFrame:
    df = pd.read_csv("vault/_export/jurisdicoes.csv")
    # Numeric conversions
    df["urgencia_deadline_dias"] = pd.to_numeric(
        df["urgencia_deadline_dias"], errors="coerce"
    )
    df["n_servicos"] = pd.to_numeric(df["n_servicos"], errors="coerce").fillna(0)
    df["n_normas_total"] = pd.to_numeric(df["n_normas_total"], errors="coerce").fillna(0)
    df["n_normas_analyzed"] = pd.to_numeric(df["n_normas_analyzed"], errors="coerce").fillna(0)
    df["maturidade_rank"] = df["maturidade_mercado"].map(MATURIDADE_ORDER).fillna(0)
    df["iso3"] = df["iso"].map(ISO2_TO_ISO3)
    df["services_list"] = df["servicos_certik_aplicaveis_csv"].fillna("").apply(
        lambda s: [x.strip() for x in s.split("|") if x.strip()]
    )
    df["frameworks_list"] = df["frameworks_aplicaveis_csv"].fillna("").apply(
        lambda s: [x.strip() for x in s.split("|") if x.strip()]
    )
    return df


@st.cache_data
def load_normas() -> pd.DataFrame:
    df = pd.read_csv("vault/_export/normas.csv")
    df["urgencia_deadline_dias"] = pd.to_numeric(
        df["urgencia_deadline_dias"], errors="coerce"
    )
    df["services_list"] = df["servicos_certik_aplicaveis_csv"].fillna("").apply(
        lambda s: [x.strip() for x in s.split("|") if x.strip()]
    )
    return df


@st.cache_data
def load_grafo() -> dict:
    return json.loads(Path("vault/_export/grafo.json").read_text(encoding="utf-8"))


def opportunity_score(row) -> float:
    """Composite ranking for the Money Chart.

    Higher = better opportunity. Three signals:
      - urgency: shorter deadline ⇒ higher (capped to 730 days)
      - service intensity: more services ⇒ higher (0..14)
      - market maturity: 'alta' regulated market = real demand ⇒ higher
    Scaled to 0..100.
    """
    # Urgency: 100 at deadline today, 0 at >=730 days (or null)
    days = row["urgencia_deadline_dias"]
    if pd.isna(days):
        urg = 20
    elif days < 0:
        urg = 100  # already past — keep visible
    else:
        urg = max(0, 100 - (days / 730) * 100)
    intensity = (row["n_servicos"] / 14) * 100
    maturity = (row["maturidade_rank"] / 3) * 100
    return round(0.4 * urg + 0.4 * intensity + 0.2 * maturity, 1)


# Sidebar — navigation
st.sidebar.markdown(f"# 🛡️ <span style='color:{CERTIK_RED}'>CertiK</span>",
                    unsafe_allow_html=True)
st.sidebar.markdown("### Market Intelligence")
page = st.sidebar.radio(
    "Navigate",
    [
        "🎯 Executive Summary",
        "🗺️ World Map",
        "📅 Deadline Timeline",
        "🛠️ By CertiK Service",
        "🌍 By Jurisdiction",
        "📖 Methodology",
    ],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.caption(
    f"Data: {len(load_jurisdicoes())} jurisdictions, "
    f"{len(load_normas())} norms, "
    f"{len(load_grafo()['edges'])} graph edges."
)
st.sidebar.caption("Built from `lukafe/scraper_obsidian_compliance` vault.")


# =========================================================================
# Page 1 — Executive Summary
# =========================================================================

def page_exec_summary():
    df = load_jurisdicoes().copy()
    df["opportunity_score"] = df.apply(opportunity_score, axis=1)
    df = df.sort_values("opportunity_score", ascending=False)

    st.title("🎯 Executive Summary")
    st.markdown(
        "**Where should CertiK expand next, and what should we sell first?**\n\n"
        "This view ranks 23 jurisdictions by an opportunity score blending "
        "urgency (deadlines), intensity (number of CertiK services triggered "
        "by local regulation) and market maturity. It's deliberately raw — "
        "no human filters applied yet."
    )

    # KPIs
    cols = st.columns(4)
    upcoming_30d = (df["urgencia_deadline_dias"] <= 30) & (df["urgencia_deadline_dias"] >= 0)
    upcoming_180d = (df["urgencia_deadline_dias"] <= 180) & (df["urgencia_deadline_dias"] >= 0)
    cols[0].metric("Jurisdictions tracked", len(df))
    cols[1].metric("Deadlines in 30 days", int(upcoming_30d.sum()))
    cols[2].metric("Deadlines in 180 days", int(upcoming_180d.sum()))
    cols[3].metric("Mature markets (`maturidade: alta`)",
                   int((df["maturidade_mercado"] == "alta").sum()))

    st.markdown("### 🏆 Top opportunities")
    top = df.head(10)[
        ["iso", "pais", "regiao", "regulador_principal",
         "deadline_principal", "urgencia_deadline_dias",
         "n_servicos", "maturidade_mercado", "opportunity_score"]
    ].rename(columns={
        "iso": "ISO", "pais": "Country", "regiao": "Region",
        "regulador_principal": "Lead Regulator",
        "deadline_principal": "Next Deadline",
        "urgencia_deadline_dias": "Days to Deadline",
        "n_servicos": "# Services",
        "maturidade_mercado": "Maturity",
        "opportunity_score": "Score (0–100)",
    })
    st.dataframe(
        top.style.background_gradient(
            subset=["Score (0–100)"], cmap="Reds",
        ).format({"Score (0–100)": "{:.1f}"}),
        use_container_width=True, hide_index=True,
    )

    # --- The Money Chart: Urgency × Intensity bubble ---
    st.markdown("### 📊 The Money Chart — Urgency × Service Intensity")
    st.caption(
        "X axis: # of CertiK services the country's regulation triggers (0–14). "
        "Y axis: urgency (days until next regulatory deadline, lower = more urgent). "
        "Bubble size: # of norms tracked. Color: market maturity."
    )

    df_plot = df.copy()
    # Replace null urgência (no deadline) with a 'far future' value for plot only.
    df_plot["days_for_plot"] = df_plot["urgencia_deadline_dias"].fillna(900)
    fig = px.scatter(
        df_plot,
        x="n_servicos", y="days_for_plot",
        size="n_normas_total", color="maturidade_mercado",
        text="iso", hover_name="pais",
        color_discrete_map={
            "alta": "#4CAF50", "media": "#FFB300",
            "baixa": "#F44336", "desconhecido": "#666",
        },
        category_orders={"maturidade_mercado": ["alta", "media", "baixa", "desconhecido"]},
        labels={
            "n_servicos": "CertiK services triggered",
            "days_for_plot": "Days until next regulatory deadline",
            "maturidade_mercado": "Market maturity",
            "n_normas_total": "# norms tracked",
        },
        size_max=55, height=600,
    )
    fig.update_traces(textposition="top center", textfont_size=11)
    fig.update_layout(
        plot_bgcolor=CERTIK_DARK, paper_bgcolor=CERTIK_DARK,
        font_color="white",
        yaxis=dict(autorange="reversed", gridcolor="#333"),
        xaxis=dict(gridcolor="#333"),
    )
    # Quadrant lines
    fig.add_shape(type="line", x0=7, x1=7, y0=0, y1=900,
                  line=dict(color="white", dash="dot", width=1))
    fig.add_shape(type="line", x0=0, x1=14, y0=180, y1=180,
                  line=dict(color="white", dash="dot", width=1))
    fig.add_annotation(x=11, y=60, text="🔥 HOT — sell now",
                       showarrow=False, font=dict(color=CERTIK_RED, size=14))
    fig.add_annotation(x=3, y=60, text="⚡ urgent but narrow",
                       showarrow=False, font=dict(color="orange", size=12))
    fig.add_annotation(x=11, y=750, text="📅 strategic — pipeline",
                       showarrow=False, font=dict(color="yellow", size=12))
    fig.add_annotation(x=3, y=750, text="🌱 watch — not now",
                       showarrow=False, font=dict(color="gray", size=12))
    st.plotly_chart(fig, use_container_width=True)

    # Top services across all jurisdictions
    st.markdown("### 🛠️ Aggregated demand by service")
    st.caption("How many jurisdictions trigger each service (out of 23).")
    svc_counter = Counter()
    for row in df.itertuples():
        for svc in row.services_list:
            svc_counter[svc] += 1
    svc_df = pd.DataFrame(
        [(SERVICE_LABELS.get(k, k), v, _category_for(k)) for k, v in svc_counter.most_common()],
        columns=["Service", "# Jurisdictions", "Category"],
    )
    fig2 = px.bar(
        svc_df, x="# Jurisdictions", y="Service", color="Category",
        orientation="h", height=520,
        color_discrete_sequence=px.colors.sequential.Reds_r,
    )
    fig2.update_layout(
        plot_bgcolor=CERTIK_DARK, paper_bgcolor=CERTIK_DARK,
        font_color="white", yaxis=dict(autorange="reversed", gridcolor="#333"),
        xaxis=dict(gridcolor="#333"),
    )
    st.plotly_chart(fig2, use_container_width=True)


def _category_for(svc: str) -> str:
    for cat, services in SERVICE_CATEGORIES.items():
        if svc in services:
            return cat
    return "Other"


# =========================================================================
# Page 2 — World Map
# =========================================================================

def page_world_map():
    df = load_jurisdicoes().copy()
    df["opportunity_score"] = df.apply(opportunity_score, axis=1)

    st.title("🗺️ World Map")
    st.markdown(
        "Choose the color metric. Darker = stronger signal. "
        "Hover for details."
    )

    metric = st.selectbox(
        "Color by",
        [
            "opportunity_score",
            "n_servicos",
            "urgencia_deadline_dias",
            "n_normas_total",
        ],
        format_func=lambda x: {
            "opportunity_score": "Opportunity Score (0–100)",
            "n_servicos": "# CertiK services triggered",
            "urgencia_deadline_dias": "Days to next deadline (lower = more urgent)",
            "n_normas_total": "# norms tracked",
        }[x],
    )
    df_plot = df.dropna(subset=["iso3"])
    color_scale = "Reds" if metric != "urgencia_deadline_dias" else "Reds_r"
    fig = px.choropleth(
        df_plot,
        locations="iso3", color=metric,
        hover_name="pais",
        hover_data={
            "regulador_principal": True,
            "regime": True,
            "maturidade_mercado": True,
            "n_servicos": True,
            "deadline_principal": True,
            "urgencia_deadline_dias": True,
            "iso3": False,
        },
        color_continuous_scale=color_scale,
        projection="natural earth",
        height=600,
    )
    fig.update_geos(bgcolor=CERTIK_DARK, showcountries=True,
                    countrycolor="#555")
    fig.update_layout(
        paper_bgcolor=CERTIK_DARK, font_color="white",
        coloraxis_colorbar=dict(title="", thickness=15),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Region breakdown
    st.markdown("### Region breakdown")
    region_df = df.groupby("regiao").agg(
        n_jurisdictions=("iso", "count"),
        avg_services=("n_servicos", "mean"),
        avg_opportunity=("opportunity_score", "mean"),
    ).round(1).reset_index().rename(columns={"regiao": "Region"})
    st.dataframe(region_df, use_container_width=True, hide_index=True)


# =========================================================================
# Page 3 — Deadline Timeline
# =========================================================================

def page_timeline():
    norms = load_normas().copy()
    juris = load_jurisdicoes().copy()

    st.title("📅 Deadline Timeline")
    st.markdown(
        "Every regulatory deadline mapped in the vault. "
        "**This is the window of opportunity.**"
    )

    # Filter norms with a real deadline
    norms_dl = norms.dropna(subset=["deadline_principal"]).copy()
    norms_dl["deadline_dt"] = pd.to_datetime(
        norms_dl["deadline_principal"], errors="coerce"
    )
    norms_dl = norms_dl.dropna(subset=["deadline_dt"])
    norms_dl["urgency_bucket"] = pd.cut(
        norms_dl["urgencia_deadline_dias"],
        bins=[-1e9, 0, 90, 365, 1e9],
        labels=["past", "≤ 90 days", "≤ 1 year", "> 1 year"],
    )

    # Region filter
    region_filter = st.multiselect(
        "Filter by region",
        sorted(juris["regiao"].dropna().unique()),
        default=sorted(juris["regiao"].dropna().unique()),
    )
    iso_in_region = juris[juris["regiao"].isin(region_filter)]["iso"].tolist()
    norms_dl = norms_dl[norms_dl["country"].isin(iso_in_region)]

    if norms_dl.empty:
        st.warning("No deadlines found for the selected filters.")
        return

    # KPIs
    cols = st.columns(4)
    cols[0].metric("Total deadlines mapped", len(norms_dl))
    cols[1].metric("Past due", int((norms_dl["urgencia_deadline_dias"] < 0).sum()))
    cols[2].metric("Within 90 days",
                   int(((norms_dl["urgencia_deadline_dias"] >= 0) &
                        (norms_dl["urgencia_deadline_dias"] <= 90)).sum()))
    cols[3].metric("Within 1 year",
                   int(((norms_dl["urgencia_deadline_dias"] >= 0) &
                        (norms_dl["urgencia_deadline_dias"] <= 365)).sum()))

    # Order norms by deadline.
    norms_dl = norms_dl.sort_values("deadline_dt")

    fig = px.scatter(
        norms_dl,
        x="deadline_dt", y="country",
        color="urgency_bucket",
        size="n_servicos",
        hover_name="title",
        hover_data={
            "regime": True, "status_regulatorio": True,
            "tipo_deadline": True, "servicos_certik_aplicaveis_csv": True,
            "country": False, "urgency_bucket": False, "deadline_dt": False,
        },
        color_discrete_map={
            "past": "#444", "≤ 90 days": "#F44336",
            "≤ 1 year": "#FFB300", "> 1 year": "#4CAF50",
        },
        category_orders={"urgency_bucket": ["past", "≤ 90 days", "≤ 1 year", "> 1 year"]},
        height=max(400, 30 * norms_dl["country"].nunique() + 100),
    )
    today = pd.to_datetime(date.today())
    fig.add_vline(x=today, line_dash="dash", line_color="white",
                  annotation_text="today", annotation_position="top")
    fig.update_layout(
        plot_bgcolor=CERTIK_DARK, paper_bgcolor=CERTIK_DARK,
        font_color="white",
        xaxis=dict(gridcolor="#333", title="Deadline date"),
        yaxis=dict(gridcolor="#333", title="Country"),
        legend_title="Urgency",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Detailed deadline table")
    table = norms_dl[
        ["country", "title", "deadline_principal", "urgencia_deadline_dias",
         "regime", "status_regulatorio", "tipo_deadline",
         "servicos_certik_aplicaveis_csv"]
    ].rename(columns={
        "country": "ISO", "title": "Norm",
        "deadline_principal": "Deadline", "urgencia_deadline_dias": "Days",
        "regime": "Regime", "status_regulatorio": "Status",
        "tipo_deadline": "Deadline Type",
        "servicos_certik_aplicaveis_csv": "Services triggered",
    })
    st.dataframe(table, use_container_width=True, hide_index=True)


# =========================================================================
# Page 4 — By CertiK Service
# =========================================================================

def page_by_service():
    juris = load_jurisdicoes().copy()
    norms = load_normas().copy()
    juris["opportunity_score"] = juris.apply(opportunity_score, axis=1)

    st.title("🛠️ By CertiK Service")
    st.markdown(
        "For each security service, see which jurisdictions trigger it and "
        "how attractive each market is right now."
    )

    cat = st.selectbox("Service category", list(SERVICE_CATEGORIES.keys()))
    services_in_cat = SERVICE_CATEGORIES[cat]
    svc = st.selectbox(
        "Service",
        services_in_cat,
        format_func=lambda x: SERVICE_LABELS.get(x, x),
    )

    # Jurisdictions that trigger this service
    juris_with_svc = juris[juris["services_list"].apply(lambda lst: svc in lst)]
    juris_with_svc = juris_with_svc.sort_values("opportunity_score", ascending=False)

    cols = st.columns(3)
    cols[0].metric("Jurisdictions where it applies", len(juris_with_svc))
    norms_with_svc = norms[norms["services_list"].apply(lambda lst: svc in lst)]
    cols[1].metric("Total norms triggering it", len(norms_with_svc))
    cols[2].metric("Mature markets among them",
                   int((juris_with_svc["maturidade_mercado"] == "alta").sum()))

    st.markdown(f"### Top markets for **{SERVICE_LABELS.get(svc, svc)}**")
    top = juris_with_svc[
        ["iso", "pais", "regiao", "regulador_principal",
         "maturidade_mercado", "deadline_principal", "urgencia_deadline_dias",
         "n_servicos", "opportunity_score"]
    ].rename(columns={
        "iso": "ISO", "pais": "Country", "regiao": "Region",
        "regulador_principal": "Lead Regulator",
        "maturidade_mercado": "Maturity",
        "deadline_principal": "Next Deadline",
        "urgencia_deadline_dias": "Days",
        "n_servicos": "All services",
        "opportunity_score": "Score",
    })
    st.dataframe(
        top.style.background_gradient(subset=["Score"], cmap="Reds").format(
            {"Score": "{:.1f}"}
        ),
        use_container_width=True, hide_index=True,
    )

    st.markdown("### Specific norms that trigger this service")
    norms_show = norms_with_svc[
        ["country", "title", "regulator", "date", "regime",
         "status_regulatorio", "deadline_principal", "escopo"]
    ].rename(columns={
        "country": "ISO", "title": "Norm", "regulator": "Regulator",
        "date": "Date", "regime": "Regime",
        "status_regulatorio": "Status",
        "deadline_principal": "Deadline", "escopo": "Scope",
    })
    st.dataframe(norms_show, use_container_width=True, hide_index=True)


# =========================================================================
# Page 5 — By Jurisdiction (drilldown)
# =========================================================================

def page_by_jurisdiction():
    juris = load_jurisdicoes().copy()
    juris["opportunity_score"] = juris.apply(opportunity_score, axis=1)
    norms = load_normas().copy()
    grafo = load_grafo()

    st.title("🌍 By Jurisdiction")
    iso = st.selectbox(
        "Pick a country",
        juris["iso"].tolist(),
        format_func=lambda x: f"{x} — {juris[juris['iso']==x]['pais'].iloc[0]}",
    )
    j_row = juris[juris["iso"] == iso].iloc[0]
    norms_country = norms[norms["country"] == iso]

    # Header
    st.markdown(f"## {j_row['pais']} ({iso}) — {j_row['regiao']}")
    cols = st.columns(5)
    cols[0].metric("Norms tracked", int(j_row["n_normas_total"]))
    cols[1].metric("LLM-analyzed", int(j_row["n_normas_analyzed"]))
    cols[2].metric("CertiK services", int(j_row["n_servicos"]))
    cols[3].metric("Maturity", j_row["maturidade_mercado"])
    cols[4].metric("Opportunity score", f"{j_row['opportunity_score']:.1f}")

    st.markdown(f"**Lead regulator:** {j_row['regulador_principal']}  ")
    if j_row["reguladores_secundarios_csv"]:
        st.markdown(f"**Secondary regulators:** {j_row['reguladores_secundarios_csv']}")
    if j_row["deadline_principal"]:
        st.markdown(
            f"**Next deadline:** {j_row['deadline_principal']} "
            f"({int(j_row['urgencia_deadline_dias'])} days)"
        )

    # Services
    st.markdown("### CertiK services triggered by this jurisdiction")
    services = j_row["services_list"]
    if services:
        rows = []
        for s in services:
            cat = _category_for(s)
            n_norms = len(norms_country[norms_country["services_list"].apply(
                lambda lst: s in lst)])
            rows.append({"Category": cat,
                         "Service": SERVICE_LABELS.get(s, s),
                         "# norms triggering it": n_norms})
        sdf = pd.DataFrame(rows).sort_values(
            ["Category", "# norms triggering it"], ascending=[True, False])
        st.dataframe(sdf, use_container_width=True, hide_index=True)
    else:
        st.info("No CertiK service triggered yet.")

    # Norms list
    st.markdown("### Underlying norms")
    show = norms_country[
        ["title", "type", "regulator", "date", "regime",
         "status_regulatorio", "deadline_principal",
         "servicos_certik_aplicaveis_csv", "escopo", "gap_ou_ambiguidade"]
    ].rename(columns={
        "title": "Title", "type": "Type", "regulator": "Regulator",
        "date": "Date", "regime": "Regime",
        "status_regulatorio": "Status",
        "deadline_principal": "Deadline",
        "servicos_certik_aplicaveis_csv": "Services",
        "escopo": "Scope (LLM-extracted)",
        "gap_ou_ambiguidade": "Gap / Ambiguity (LLM-extracted)",
    })
    st.dataframe(show, use_container_width=True, hide_index=True)

    # Connected jurisdictions / frameworks (graph edges)
    st.markdown("### Connected frameworks (inherits from / inspires)")
    edges = [
        e for e in grafo["edges"]
        if e["source"] == iso
        or any(e["source"] == n["id"] and n.get("country") == iso
               for n in grafo["nodes"])
    ]
    derived = [e for e in edges if e["tipo_relacao"] == "derivado_de"]
    inspired = [e for e in edges if e["tipo_relacao"] == "inspirado_em"]
    cross_ref = [e for e in edges if e["tipo_relacao"] == "referencia_cruzada"]
    cols2 = st.columns(3)
    cols2[0].metric("Direct implementations (derivado_de)", len(derived))
    cols2[1].metric("Soft inspirations (inspirado_em)", len(inspired))
    cols2[2].metric("Cross-citations", len(cross_ref))

    if derived:
        st.caption("Derived from:")
        for e in derived[:10]:
            st.markdown(f"- **{e['target']}** — {e.get('justificativa', '')}")
    if inspired:
        st.caption("Inspired by:")
        for e in inspired[:10]:
            st.markdown(f"- **{e['target']}** — {e.get('justificativa', '')}")


# =========================================================================
# Page 6 — Methodology
# =========================================================================

def page_methodology():
    st.title("📖 Methodology")
    st.markdown(
        """
This dashboard is built from an Obsidian vault that scraped 1267 crypto-regulation
norms across 23 jurisdictions. Each norm was:

1. **Discovered** via Gemini web-search (per-country seeding from a curated matrix).
2. **Scraped** from primary sources (official gazettes, regulator portals).
3. **Translated** to English when source was non-English (auto + preserved original).
4. **Analyzed** by Gemini 2.5 Pro to extract:
   - `regime` (licensing / registration / ban / consultation / silent)
   - `status_regulatorio` (in-force / implementing / consultation / proposed)
   - `deadline_principal` (next regulatory date)
   - 7 boolean `exige_*` triggers (audit / pentest / PoR / KYT / custody / FV / cert)
   - 1–2 sentence `escopo` and `gap_ou_ambiguidade`

### Confidence

Each field is tagged `alta` / `media` / `baixa`. Default after auto-extraction
is `media` — manual review can elevate to `alta`. Null values are preferred to
guesses (so a missing `regime` ≠ "no regime", just "model didn't extract one
with confidence").

### Service triggers

Booleans + keyword scan map onto 14 CertiK services across 3 categories:

- **Security Auditing**: Smart Contract Audit, L1 Chain Audit, Penetration Testing, Formal Verification
- **Compliance & Monitoring**: SkyInsights (AML/KYT), Skynet (Threat Monitoring), Proof of Reserves, Skyshield (Bug Bounty), Performance Testing, Due Diligence, Incident Response
- **Advisory & Certification**: Independent Certification, Security Guidance, Regulatory Compliance Support

### Opportunity score (0–100)

A composite ranking, not a final answer. Weights (subject to tuning):
- 40% **urgency** — days to next deadline (closer = higher; null = neutral)
- 40% **service intensity** — # of services triggered (0–14)
- 20% **market maturity** — heuristic: # of regulators × # of analyzed norms × oldest norm age

### Known limitations

- `competidores_ativos` and `forca_relacionamento_certik` are intentionally empty
  — they require human input from the BD team.
- 2 jurisdictions (`IN`, `SE`) have only stub norms — analysis returned no signals.
- `regime` extraction succeeded on ~40% of analyzed norms (conservative prompt).
- `deadline_principal` extracted on ~20% (only when text is explicit).

### Raw data

Files under `vault/_export/`:
- `jurisdicoes.csv` — 23 rows, 30 columns (one per country)
- `normas.csv` — 1267 rows (every norm with full frontmatter flattened)
- `grafo.json` — 1290 nodes + 2997 edges (typed: derivado_de, inspirado_em,
  referencia_cruzada, citation, semantic, aplica_se_a, exige_servico)
        """
    )


# ---------- Dispatcher ----------

if page.startswith("🎯"):
    page_exec_summary()
elif page.startswith("🗺️"):
    page_world_map()
elif page.startswith("📅"):
    page_timeline()
elif page.startswith("🛠️"):
    page_by_service()
elif page.startswith("🌍"):
    page_by_jurisdiction()
elif page.startswith("📖"):
    page_methodology()
