"""
ChurnRadar – Pipeline de calcul des scores de churn.

Utilisation :
    python pipeline.py
    OPENWEATHER_API_KEY=<clé> python pipeline.py
"""

import os
import re
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
DB_PATH = ROOT / "churnradar.db"
SCHEMA_PATH = ROOT / "schema.sql"
DATA_DIR = ROOT / "data"

# ---------------------------------------------------------------------------
# Config OpenWeatherMap
# ---------------------------------------------------------------------------

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# ---------------------------------------------------------------------------
# Constantes de normalisation
# Chaque composante est ramenée à [0, 1] avant pondération.
# ---------------------------------------------------------------------------

INACTIVITE_MAX_JOURS = 180   # 180 j d'inactivité → risque inactivité = 1.0
COMMANDES_MAX        = 5     # 5+ commandes       → risque fréquence   = 0.0
PANIER_MAX_EUR       = 500.0 # 500 €+ de panier   → risque valeur      = 0.0
SESSIONS_MAX         = 5     # 5+ sessions        → risque engagement  = 0.0

# ---------------------------------------------------------------------------
# Actions recommandées par niveau de risque × segment client
# ---------------------------------------------------------------------------

_ACTIONS: dict[str, dict[str, str]] = {
    "faible": {
        "Particulier":  "Newsletter fidélité + offre personnalisée",
        "PME":          "Programme de fidélité PME",
        "Startup":      "Onboarding avancé + upsell",
        "Grand compte": "Account manager dédié",
    },
    "moyen": {
        "Particulier":  "Campagne email de réactivation",
        "PME":          "Appel commercial + offre de remise",
        "Startup":      "Webinaire exclusif + essai gratuit",
        "Grand compte": "Revue de compte + proposition de valeur",
    },
    "eleve": {
        "Particulier":  "Offre de réactivation 20% + appel",
        "PME":          "Remise exceptionnelle 25% PME",
        "Startup":      "Offre découverte nouveau produit",
        "Grand compte": "Réunion stratégique compte grand",
    },
    "critique": {
        "Particulier":  "Dernière tentative de contact avant archivage",
        "PME":          "Campagne win-back PME urgente",
        "Startup":      "Archivage programmé sauf réponse",
        "Grand compte": "Escalade direction commerciale",
    },
}

# ---------------------------------------------------------------------------
# Données météo de simulation (toutes les villes du jeu de données)
# ---------------------------------------------------------------------------

_METEO_SIM: dict[str, dict] = {
    "Paris":            {"temp": 18.5, "description": "nuageux",              "humidite": 72},
    "Lyon":             {"temp": 20.1, "description": "ensoleillé",           "humidite": 58},
    "Marseille":        {"temp": 23.4, "description": "ensoleillé",           "humidite": 55},
    "Toulouse":         {"temp": 21.8, "description": "partiellement nuageux","humidite": 60},
    "Nantes":           {"temp": 16.9, "description": "pluie légère",         "humidite": 80},
    "Strasbourg":       {"temp": 17.3, "description": "couvert",              "humidite": 75},
    "Bordeaux":         {"temp": 19.6, "description": "ensoleillé",           "humidite": 62},
    "Lille":            {"temp": 15.2, "description": "pluie légère",         "humidite": 82},
    "Rennes":           {"temp": 16.4, "description": "couvert",              "humidite": 78},
    "Nice":             {"temp": 24.7, "description": "ensoleillé",           "humidite": 50},
    "Montpellier":      {"temp": 22.5, "description": "ensoleillé",           "humidite": 53},
    "Grenoble":         {"temp": 18.0, "description": "partiellement nuageux","humidite": 65},
    "Dijon":            {"temp": 17.8, "description": "couvert",              "humidite": 70},
    "Reims":            {"temp": 16.1, "description": "nuageux",              "humidite": 74},
    "Angers":           {"temp": 17.5, "description": "pluie légère",         "humidite": 79},
    "Tours":            {"temp": 18.2, "description": "partiellement nuageux","humidite": 67},
    "Limoges":          {"temp": 16.8, "description": "couvert",              "humidite": 76},
    "Metz":             {"temp": 15.9, "description": "nuageux",              "humidite": 73},
    "Amiens":           {"temp": 14.8, "description": "pluie légère",         "humidite": 83},
    "Clermont-Ferrand": {"temp": 17.4, "description": "partiellement nuageux","humidite": 68},
    "Caen":             {"temp": 15.6, "description": "couvert",              "humidite": 80},
    "Orléans":          {"temp": 17.9, "description": "nuageux",              "humidite": 69},
    "Besançon":         {"temp": 16.5, "description": "partiellement nuageux","humidite": 71},
    "Poitiers":         {"temp": 18.0, "description": "partiellement nuageux","humidite": 66},
    "Rouen":            {"temp": 15.3, "description": "pluie légère",         "humidite": 81},
    "Brest":            {"temp": 13.8, "description": "pluie",                "humidite": 87},
    "Toulon":           {"temp": 23.1, "description": "ensoleillé",           "humidite": 52},
    "Perpignan":        {"temp": 25.2, "description": "ensoleillé",           "humidite": 48},
    "Le Havre":         {"temp": 14.9, "description": "couvert",              "humidite": 82},
    "Nancy":            {"temp": 16.2, "description": "nuageux",              "humidite": 72},
}


# ---------------------------------------------------------------------------


def init_db() -> sqlite3.Connection:
    """
    Ouvre (ou crée) churnradar.db.

    Stratégie idempotente :
      – Les CREATE TABLE/VIEW IF NOT EXISTS sont toujours rejoués (sans effet
        si les objets existent déjà).
      – Les INSERT sont joués une seule fois, uniquement si la table clients
        est vide, pour ne pas dupliquer les données initiales.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    # Découpe le script en instructions individuelles
    raw_stmts = re.split(r";\s*(?:\n|$)", schema)

    ddl_stmts: list[str] = []
    insert_stmts: list[str] = []
    for raw in raw_stmts:
        # Retire les lignes de commentaires pour la classification
        clean = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("--")
        ).strip()
        if not clean:
            continue
        if re.match(r"CREATE", clean, re.I):
            ddl_stmts.append(clean)
        elif re.match(r"INSERT", clean, re.I):
            insert_stmts.append(clean)

    for stmt in ddl_stmts:
        conn.execute(stmt)

    already_loaded = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    if already_loaded == 0:
        for stmt in insert_stmts:
            conn.execute(stmt)
        conn.commit()
        print(f"[init_db] {DB_PATH.name} initialisée – {len(insert_stmts)} insertions jouées")
    else:
        conn.commit()
        print(f"[init_db] {DB_PATH.name} existante – {already_loaded} clients en base")

    return conn


def calculer_score_churn(row: dict) -> dict:
    """
    Calcule un score de churn pondéré entre 0.0 (aucun risque) et 1.0
    (churn quasi-certain) selon quatre composantes :

        Inactivité      40 %  – jours sans session
        Fréquence achat 25 %  – nombre total de commandes
        Panier moyen    15 %  – valeur moyenne par commande
        Engagement web  20 %  – nombre total de sessions

    Retourne un dict avec score_churn, segment_risque et action_recommandee.
    """
    jours    = max(0,   int(row.get("jours_inactif") or 0))
    commandes = max(0,  int(row.get("nb_commandes")  or 0))
    panier   = max(0.0, float(row.get("panier_moyen") or 0.0))
    sessions = max(0,   int(row.get("nb_sessions")   or 0))
    segment  = row.get("segment", "Particulier")

    # Chaque terme = composante normalisée [0,1] × poids
    inactivite = min(jours    / INACTIVITE_MAX_JOURS, 1.0) * 0.40
    frequence  = max(0.0, 1.0 - commandes / COMMANDES_MAX) * 0.25
    valeur     = max(0.0, 1.0 - panier    / PANIER_MAX_EUR) * 0.15
    engagement = max(0.0, 1.0 - sessions  / SESSIONS_MAX)  * 0.20

    score = round(min(inactivite + frequence + valeur + engagement, 1.0), 4)

    if score < 0.25:
        segment_risque = "faible"
    elif score < 0.50:
        segment_risque = "moyen"
    elif score < 0.75:
        segment_risque = "eleve"
    else:
        segment_risque = "critique"

    action = _ACTIONS[segment_risque].get(segment, _ACTIONS[segment_risque]["Particulier"])

    return {
        "score_churn":        score,
        "segment_risque":     segment_risque,
        "action_recommandee": action,
    }


def get_meteo(ville: str) -> dict:
    """
    Retourne la météo actuelle (température, description, humidité).

    Tente d'abord l'API OpenWeatherMap si OPENWEATHER_API_KEY est défini.
    En l'absence de clé ou en cas d'erreur réseau, bascule sur des données
    simulées pour les 30 villes du jeu de données.
    """
    if OPENWEATHER_API_KEY:
        try:
            resp = requests.get(
                OPENWEATHER_URL,
                params={
                    "q":      f"{ville},FR",
                    "appid":  OPENWEATHER_API_KEY,
                    "units":  "metric",
                    "lang":   "fr",
                },
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "meteo_temp":     data["main"]["temp"],
                "meteo_desc":     data["weather"][0]["description"],
                "meteo_humidite": data["main"]["humidity"],
                "meteo_source":   "openweathermap",
            }
        except Exception as exc:
            print(f"[get_meteo] API indisponible pour {ville!r} ({exc}) → simulation")

    sim = _METEO_SIM.get(ville, {"temp": 18.0, "description": "variable", "humidite": 70})
    return {
        "meteo_temp":     sim["temp"],
        "meteo_desc":     sim["description"],
        "meteo_humidite": sim["humidite"],
        "meteo_source":   "simulation",
    }


def run_pipeline() -> pd.DataFrame:
    """
    Pipeline principal :
      1. Initialise la base SQLite via schema.sql
      2. Charge v_client_resume
      3. Calcule le score de churn pour chaque client
      4. Récupère la météo par ville (API ou simulation)
      5. Met à jour la table churn_scores (upsert)
      6. Exporte un CSV horodaté dans data/

    Retourne le DataFrame complet avec tous les résultats.
    """
    conn  = init_db()
    today = date.today().isoformat()

    df = pd.read_sql_query("SELECT * FROM v_client_resume", conn)
    print(f"[pipeline] {len(df)} clients chargés depuis v_client_resume")

    # Une requête météo par ville unique
    villes_uniques = df["ville"].unique()
    meteo_cache = {v: get_meteo(v) for v in villes_uniques}
    source = meteo_cache[villes_uniques[0]]["meteo_source"]
    print(f"[pipeline] Météo récupérée pour {len(meteo_cache)} villes ({source})")

    # Calcul des scores et construction du DataFrame résultat
    records: list[dict] = []
    for _, row in df.iterrows():
        d     = row.to_dict()
        churn = calculer_score_churn(d)
        meteo = meteo_cache.get(d["ville"], {})
        records.append({
            "client_id":          int(d["client_id"]),
            "nom":                d["nom"],
            "email":              d["email"],
            "ville":              d["ville"],
            "segment":            d["segment"],
            "jours_inactif":      int(d["jours_inactif"]),
            "nb_commandes":       int(d["nb_commandes"]),
            "chiffre_affaires":   float(d["chiffre_affaires"]),
            "panier_moyen":       float(d["panier_moyen"]),
            "nb_sessions":        int(d["nb_sessions"]),
            "derniere_session":   d["derniere_session"],
            "score_churn":        churn["score_churn"],
            "segment_risque":     churn["segment_risque"],
            "action_recommandee": churn["action_recommandee"],
            "date_calcul":        today,
            **meteo,
        })

    # ── Upsert dans churn_scores ─────────────────────────────────────────────
    conn.cursor().executemany(
        """
        INSERT INTO churn_scores
            (client_id, score_churn, segment_risque, date_calcul,
             jours_inactif, nb_commandes, panier_moyen, action_recommandee)
        VALUES
            (:client_id, :score_churn, :segment_risque, :date_calcul,
             :jours_inactif, :nb_commandes, :panier_moyen, :action_recommandee)
        ON CONFLICT(client_id) DO UPDATE SET
            score_churn        = excluded.score_churn,
            segment_risque     = excluded.segment_risque,
            date_calcul        = excluded.date_calcul,
            jours_inactif      = excluded.jours_inactif,
            nb_commandes       = excluded.nb_commandes,
            panier_moyen       = excluded.panier_moyen,
            action_recommandee = excluded.action_recommandee
        """,
        records,
    )
    conn.commit()
    conn.close()
    print(f"[pipeline] churn_scores mis à jour pour {len(records)} clients")

    # ── Export CSV ───────────────────────────────────────────────────────────
    DATA_DIR.mkdir(exist_ok=True)
    csv_path = DATA_DIR / f"churn_export_{today.replace('-', '')}.csv"
    result_df = pd.DataFrame(records)
    result_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[pipeline] Export → {csv_path.relative_to(ROOT)}")

    return result_df


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    df = run_pipeline()

    top5 = df.nlargest(5, "score_churn").reset_index(drop=True)

    SEP  = "╠" + "═" * 72 + "╣"
    HAUT = "╔" + "═" * 72 + "╗"
    BAS  = "╚" + "═" * 72 + "╝"

    print()
    print(HAUT)
    print("║{:^72}║".format("CHURNRADAR – TOP 5 CLIENTS À RISQUE"))
    print(SEP)
    for i, row in top5.iterrows():
        badge = {"faible": "🟢", "moyen": "🟡", "eleve": "🟠", "critique": "🔴"}.get(
            row["segment_risque"], "⚪"
        )
        line = (
            f"  {i+1}. {row['nom']:<22}"
            f"  score {row['score_churn']:.4f}"
            f"  {row['segment_risque']:<8}"
            f"  {row['jours_inactif']:>3}j inactif"
        )
        print(f"║ {badge} {line:<69}║")
    print(BAS)

    # Répartition par segment de risque
    print()
    print("  Répartition des risques :")
    counts = df["segment_risque"].value_counts()
    total  = len(df)
    for seg, couleur in [("faible", "🟢"), ("moyen", "🟡"), ("eleve", "🟠"), ("critique", "🔴")]:
        n   = counts.get(seg, 0)
        pct = n / total * 100
        bar = "█" * n + "░" * (10 - min(n, 10))
        print(f"  {couleur} {seg:<10}  {bar}  {n:>2}/{total}  ({pct:.0f}%)")

    # Actions recommandées pour le top 5
    print()
    print("  Actions pour le top 5 :")
    for _, row in top5.iterrows():
        print(f"  → {row['nom']:<22}  {row['action_recommandee']}")
    print()
