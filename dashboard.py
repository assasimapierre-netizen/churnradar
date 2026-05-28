"""
ChurnRadar – Dashboard Streamlit
Lancement : streamlit run dashboard.py
"""

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="ChurnRadar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT    = Path(__file__).parent
DB_PATH = ROOT / "churnradar.db"

# ---------------------------------------------------------------------------
# Palette de couleurs (Plotly + CSS)
# ---------------------------------------------------------------------------

PALETTE = {
    "faible":   "#2ecc71",
    "moyen":    "#f39c12",
    "eleve":    "#e67e22",
    "critique": "#e74c3c",
}

PALETTE_CSS = {
    "faible":   "background-color:#d4f5e2; color:#155724",
    "moyen":    "background-color:#fff3cd; color:#856404",
    "eleve":    "background-color:#ffe8cc; color:#7b4106",
    "critique": "background-color:#fbd5d8; color:#842029",
}

LABEL_RISQUE = {
    "faible":   "🟢 Faible",
    "moyen":    "🟡 Moyen",
    "eleve":    "🟠 Élevé",
    "critique": "🔴 Critique",
}


def _score_css(val: float) -> str:
    """Dégradé CSS vert→rouge pour la colonne Score (sans matplotlib)."""
    v = max(0.0, min(1.0, float(val)))
    r = int(220 * v + 40 * (1 - v))
    g = int(40  * v + 200 * (1 - v))
    text = "white" if v > 0.55 else "#1a1a1a"
    return f"background-color: rgb({r},{g},60); color:{text}; font-weight:600"

# ---------------------------------------------------------------------------
# Chargement des données (mis en cache 5 min)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_clients() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """
        SELECT
            v.client_id, v.nom, v.email, v.ville, v.segment,
            v.date_inscription,
            v.nb_commandes, v.chiffre_affaires, v.panier_moyen,
            v.derniere_commande, v.nb_sessions, v.duree_session_moyenne,
            v.derniere_session,
            cs.score_churn, cs.segment_risque, cs.jours_inactif,
            cs.action_recommandee, cs.date_calcul
        FROM v_client_resume v
        JOIN churn_scores cs ON cs.client_id = v.client_id
        ORDER BY cs.score_churn DESC
        """,
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_ca_mensuel(client_ids: tuple) -> pd.DataFrame:
    """Chargement du CA mensuel filtré sur un ensemble de client_id."""
    if not client_ids:
        return pd.DataFrame(columns=["mois", "ca", "nb_commandes"])
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(client_ids))
    df = pd.read_sql(
        f"""
        SELECT
            strftime('%Y-%m', date_commande) AS mois,
            SUM(montant)                     AS ca,
            COUNT(*)                         AS nb_commandes
        FROM commandes
        WHERE statut = 'livree'
          AND client_id IN ({placeholders})
        GROUP BY mois
        ORDER BY mois
        """,
        conn,
        params=list(client_ids),
    )
    conn.close()
    return df

# ---------------------------------------------------------------------------
# Application principale
# ---------------------------------------------------------------------------

def main() -> None:
    df_all = load_clients()

    if df_all.empty:
        st.error(
            "⚠️ Base de données introuvable ou vide.  \n"
            "Lancez d'abord **`python pipeline.py`** pour initialiser ChurnRadar."
        )
        return

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("# 📡 ChurnRadar")
        st.markdown("*Analyse prédictive du churn client*")
        st.divider()

        st.markdown("### Filtres")

        selected_segments = st.multiselect(
            "Segment de risque",
            options=list(LABEL_RISQUE.keys()),
            default=list(LABEL_RISQUE.keys()),
            format_func=lambda s: LABEL_RISQUE[s],
        )

        villes_dispo = sorted(df_all["ville"].unique())
        selected_villes = st.multiselect(
            "Ville",
            options=villes_dispo,
            default=villes_dispo,
        )

        segments_clients = sorted(df_all["segment"].unique())
        selected_segments_clients = st.multiselect(
            "Segment client",
            options=segments_clients,
            default=segments_clients,
        )

        st.divider()
        st.caption(f"Mise à jour : {df_all['date_calcul'].max()}")

    # ── Filtrage ─────────────────────────────────────────────────────────────
    df = df_all[
        df_all["segment_risque"].isin(selected_segments)
        & df_all["ville"].isin(selected_villes)
        & df_all["segment"].isin(selected_segments_clients)
    ]

    # ── En-tête ───────────────────────────────────────────────────────────────
    st.title("📡 ChurnRadar – Tableau de bord")
    st.caption(
        f"Analyse au **{date.today().strftime('%d/%m/%Y')}** · "
        f"**{len(df)}** clients sélectionnés sur **{len(df_all)}**"
    )

    if df.empty:
        st.warning("Aucun client ne correspond aux filtres sélectionnés.")
        return

    st.divider()

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    n_crit  = int((df["segment_risque"] == "critique").sum())
    pct_crit = f"{n_crit / len(df) * 100:.0f} % du total"
    score_moy = df["score_churn"].mean()
    inact_moy = df["jours_inactif"].mean()

    # Comparaison vs base complète pour les deltas
    delta_score = score_moy - df_all["score_churn"].mean()
    delta_inact = inact_moy - df_all["jours_inactif"].mean()

    k1.metric("👥 Clients analysés",   len(df),   f"{len(df_all) - len(df):+d} hors sélection")
    k2.metric("🔴 Clients critiques",  n_crit,    pct_crit)
    k3.metric("📊 Score moyen",        f"{score_moy:.3f}", f"{delta_score:+.3f} vs total")
    k4.metric("⏱️ Inactivité moyenne", f"{inact_moy:.0f} j", f"{delta_inact:+.0f} j vs total")

    st.divider()

    # ── Ligne 1 : Camembert + Scatter ─────────────────────────────────────────
    col_pie, col_scatter = st.columns([1, 2], gap="large")

    with col_pie:
        st.subheader("Répartition des risques")
        counts = (
            df["segment_risque"]
            .value_counts()
            .reindex(["critique", "eleve", "moyen", "faible"], fill_value=0)
            .reset_index()
        )
        counts.columns = ["segment_risque", "count"]

        fig_pie = px.pie(
            counts,
            names="segment_risque",
            values="count",
            color="segment_risque",
            color_discrete_map=PALETTE,
            hole=0.42,
        )
        fig_pie.update_traces(
            textinfo="percent+label",
            textfont_size=13,
            pull=[0.04] * 4,
        )
        fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_scatter:
        st.subheader("Score churn vs Jours d'inactivité")
        df_s = df.copy()
        df_s["taille"] = df_s["panier_moyen"].clip(lower=20)

        fig_scat = px.scatter(
            df_s,
            x="jours_inactif",
            y="score_churn",
            size="taille",
            size_max=50,
            color="segment_risque",
            color_discrete_map=PALETTE,
            hover_name="nom",
            hover_data={
                "ville":              True,
                "segment":            True,
                "nb_commandes":       True,
                "panier_moyen":       ":.2f",
                "taille":             False,
                "action_recommandee": True,
            },
            labels={
                "jours_inactif":  "Jours d'inactivité",
                "score_churn":    "Score de churn",
                "segment_risque": "Risque",
                "panier_moyen":   "Panier moy. (€)",
            },
        )
        fig_scat.update_layout(
            xaxis=dict(title="Jours d'inactivité", showgrid=True, gridcolor="#f0f0f0"),
            yaxis=dict(title="Score de churn", range=[-0.02, 1.05], showgrid=True, gridcolor="#f0f0f0"),
            legend=dict(title="Risque", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=10, b=0),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig_scat, use_container_width=True)

    st.divider()

    # ── Histogramme CA mensuel ────────────────────────────────────────────────
    st.subheader("📈 Chiffre d'affaires mensuel (commandes livrées)")

    client_ids = tuple(int(i) for i in df["client_id"].tolist())
    df_ca = load_ca_mensuel(client_ids)

    if not df_ca.empty:
        fig_ca = px.bar(
            df_ca,
            x="mois",
            y="ca",
            hover_data={"nb_commandes": True},
            labels={
                "mois":         "Mois",
                "ca":           "CA (€)",
                "nb_commandes": "Nb commandes",
            },
            color_discrete_sequence=["#3498db"],
            text_auto=".0f",
        )
        fig_ca.update_traces(textposition="outside", textfont_size=11)
        fig_ca.update_layout(
            xaxis_title="Mois",
            yaxis_title="CA (€)",
            plot_bgcolor="white",
            yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
            margin=dict(t=10, b=0),
        )
        st.plotly_chart(fig_ca, use_container_width=True)
    else:
        st.info("Aucune commande livrée pour la sélection actuelle.")

    st.divider()

    # ── Tableau ───────────────────────────────────────────────────────────────
    st.subheader("📋 Clients classés par score de churn décroissant")

    COLS = {
        "nom":              "Client",
        "ville":            "Ville",
        "segment":          "Segment",
        "segment_risque":   "Risque",
        "score_churn":      "Score",
        "jours_inactif":    "Inactivité (j)",
        "nb_commandes":     "Commandes",
        "panier_moyen":     "Panier (€)",
        "chiffre_affaires": "CA total (€)",
        "action_recommandee": "Action recommandée",
    }

    df_table = df[list(COLS.keys())].rename(columns=COLS)

    styler = (
        df_table.style
        .format({
            "Score":       "{:.4f}",
            "Panier (€)":  "{:.2f}",
            "CA total (€)": "{:.2f}",
        })
        .map(lambda v: PALETTE_CSS.get(v, ""), subset=["Risque"])
        .map(_score_css, subset=["Score"])
        .set_properties(**{"text-align": "left", "font-size": "13px"})
        .hide(axis="index")
    )

    st.dataframe(styler, use_container_width=True, height=460)

    # ── Export CSV ────────────────────────────────────────────────────────────
    COLS_CSV = [
        "client_id", "nom", "email", "ville", "segment",
        "score_churn", "segment_risque", "jours_inactif",
        "nb_commandes", "panier_moyen", "chiffre_affaires",
        "derniere_session", "action_recommandee", "date_calcul",
    ]
    csv_bytes = df[COLS_CSV].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    filename  = f"churn_export_{date.today().strftime('%Y%m%d')}.csv"

    st.download_button(
        label="📥 Exporter la sélection en CSV",
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
        use_container_width=False,
    )


if __name__ == "__main__":
    main()
