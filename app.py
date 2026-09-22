
import streamlit as st
import pandas as pd
import re
import time
from datetime import datetime
from pathlib import Path

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

APP_DIR = Path(__file__).parent
LOG_FILE = APP_DIR / "run_log.csv"
TEST_FILE = APP_DIR / "test_accounts.csv"

st.set_page_config(page_title="Nepsis Account Qualifier", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

# -----------------------------
# Rules
# -----------------------------
STRONG_SIGNALS = {
    "FINANCING / REFINANCING": [
        "financing", "refinancing", "financement", "refinancement",
        "project finance", "debt financing", "green loan", "credit facility",
        "syndicated loan", "facility", "funding", "fundraise"
    ],
    "M&A / PORTFOLIO TRANSACTION": [
        "acquisition", "acquires", "acquired", "m&a", "merger", "sale of portfolio",
        "portfolio sale", "cession", "acquisition de", "joint venture", "investment"
    ],
    "PROJECT FINANCE HIRING": [
        "project finance analyst", "project finance manager", "head of project finance",
        "analyste financement", "financement de projet", "project finance associate",
        "investment manager"
    ],
}

MEDIUM_SIGNALS = {
    "TENDER / AWARD": [
        "winner", "awarded", "lauréat", "appel d'offres", "tender", "selected project"
    ],
    "PERMIT / CONSTRUCTION": [
        "permit", "permis", "construction", "mise en service", "commissioning",
        "ready-to-build", "rtb", "under construction"
    ],
    "PORTFOLIO GROWTH": [
        "portfolio", "pipeline", "mw", "gw", "projects", "projets", "solar", "wind",
        "photovoltaic", "renewable", "battery", "bess", "éolien", "photovoltaïque"
    ]
}

RENEWABLE_TERMS = [
    "renewable", "solar", "wind", "photovoltaic", "battery", "bess",
    "énergies renouvelables", "solaire", "éolien", "photovoltaïque"
]

PERSONA_TERMS = {
    "CFO / Finance": ["cfo", "chief financial officer", "finance director", "directeur financier"],
    "Project Finance": ["project finance", "financement de projet", "project finance analyst", "project finance manager"],
    "Investment / M&A": ["investment", "m&a", "mergers", "acquisition", "investment manager"],
    "Development": ["development director", "head of development", "développement", "project development"],
}

MONTHS = {
    "jan":1,"janvier":1,"january":1,"feb":2,"février":2,"february":2,"mar":3,"mars":3,"march":3,
    "apr":4,"avril":4,"april":4,"may":5,"mai":5,"jun":6,"juin":6,"june":6,"jul":7,"juillet":7,"july":7,
    "aug":8,"août":8,"august":8,"sep":9,"sept":9,"septembre":9,"september":9,"oct":10,"octobre":10,"october":10,
    "nov":11,"novembre":11,"november":11,"dec":12,"déc":12,"décembre":12,"december":12
}

def extract_date(text):
    t = text.lower()
    # dd/mm/yyyy
    m = re.search(r"\b([0-3]?\d)[/.-]([01]?\d)[/.-](20\d{2})\b", t)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except:
            pass
    # month name yyyy, optionally day
    for name, num in MONTHS.items():
        m = re.search(rf"\b([0-3]?\d)?\s*{re.escape(name)}[a-zéû\.]*\s+(20\d{{2}})\b", t)
        if m:
            day = int(m.group(1)) if m.group(1) else 1
            try:
                return datetime(int(m.group(2)), num, day)
            except:
                pass
    return None

def classify_signal(text):
    txt = text.lower()
    strong = []
    medium = []
    for signal, kws in STRONG_SIGNALS.items():
        if any(k in txt for k in kws):
            strong.append(signal)
    for signal, kws in MEDIUM_SIGNALS.items():
        if any(k in txt for k in kws):
            medium.append(signal)
    return strong, medium

def detect_persona(text):
    txt = text.lower()
    found = []
    for persona, kws in PERSONA_TERMS.items():
        if any(k in txt for k in kws):
            found.append(persona)
    return found

def search_web(company):
    if DDGS is None:
        raise RuntimeError("Le package 'ddgs' n'est pas installé. Lance: pip install -r requirements.txt")
    queries = [
        f'"{company}" financing refinancing project finance renewable 2026',
        f'"{company}" acquisition investment portfolio renewable 2026',
        f'"{company}" "project finance" job OR analyst OR manager 2026',
        f'"{company}" awarded tender permit construction renewable 2026',
    ]
    rows = []
    seen = set()
    with DDGS() as ddgs:
        for q in queries:
            try:
                results = ddgs.text(q, max_results=6)
            except Exception:
                results = []
            for r in results:
                url = (r.get("href") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                title = (r.get("title") or "").strip()
                body = (r.get("body") or "").strip()
                text = f"{title} {body}"
                strong, medium = classify_signal(text)
                personas = detect_persona(text)
                d = extract_date(text)
                rows.append({
                    "title": title,
                    "snippet": body,
                    "url": url,
                    "date": d.strftime("%Y-%m-%d") if d else "",
                    "strong_signals": " | ".join(strong),
                    "medium_signals": " | ".join(medium),
                    "persona_evidence": " | ".join(personas),
                })
    return pd.DataFrame(rows)

def score_company(company, df):
    if df.empty:
        return {
            "company": company, "score": 0, "status": "INSUFFICIENT",
            "reason": "Aucune preuve publique récupérée.",
            "persona": "Human review",
            "gesture": "Ne pas contacter : enrichir les preuves.",
            "n_sources": 0, "strong_count": 0, "medium_count": 0
        }

    now = datetime.now()
    strong_count = 0
    medium_count = 0
    recent_strong = 0
    fit_hits = 0
    maturity_hits = 0
    persona_hits = 0

    evidence_bits = []

    for _, r in df.iterrows():
        txt = f"{r['title']} {r['snippet']}".lower()
        strong = [x for x in str(r["strong_signals"]).split(" | ") if x]
        medium = [x for x in str(r["medium_signals"]).split(" | ") if x]
        strong_count += len(strong)
        medium_count += len(medium)
        if any(term in txt for term in RENEWABLE_TERMS):
            fit_hits += 1
        if any(k in txt for k in ["portfolio","pipeline","project","projet","mw","gw","construction","financing","financement"]):
            maturity_hits += 1
        if str(r["persona_evidence"]).strip():
            persona_hits += 1
        if strong:
            is_recent = False
            if r["date"]:
                try:
                    dt = datetime.strptime(r["date"], "%Y-%m-%d")
                    is_recent = (now - dt).days <= 550
                except:
                    pass
            if is_recent or not r["date"]:
                recent_strong += 1

    # Score transparent: 10 max
    signal_score = 4 if recent_strong >= 1 else (3 if strong_count >= 1 else (2 if medium_count >= 1 else 0))
    fit_score = 3 if fit_hits >= 2 else (2 if fit_hits == 1 else 0)
    maturity_score = 2 if maturity_hits >= 2 else (1 if maturity_hits == 1 else 0)
    persona_score = 1 if persona_hits >= 1 else 0
    score = min(10, signal_score + fit_score + maturity_score + persona_score)

    # Require minimum evidence to contact
    n_sources = len(df)
    has_strong = strong_count >= 1

    if n_sources < 2:
        status = "INSUFFICIENT"
    elif score >= 8 and has_strong:
        status = "CONTACT"
    elif score >= 5:
        status = "WATCH"
    else:
        status = "INSUFFICIENT"

    # Persona + gesture
    all_text = " ".join((df["title"].fillna("") + " " + df["snippet"].fillna("")).tolist()).lower()
    if any(k in all_text for k in ["m&a","acquisition","investment","portfolio sale","joint venture"]):
        persona = "Head of M&A / Investment ou CFO"
        gesture = "Outreach contextualisé sur la transaction/portefeuille ; angle : accélérer analyse, modélisation et closing financier."
    elif any(k in all_text for k in ["project finance","financement de projet","refinancing","refinancement","financing","financement"]):
        persona = "Head of Project Finance / CFO"
        gesture = "Outreach contextualisé sur le financement récent ; angle : réduire le temps de préparation, revue et documentation du closing."
    elif any(k in all_text for k in ["analyste financement","project finance analyst","project finance manager"]):
        persona = "Head of Project Finance / Finance Director"
        gesture = "Outreach lié au recrutement project finance ; angle : absorber plus de projets sans augmenter proportionnellement la charge opérationnelle."
    elif any(k in all_text for k in ["awarded","lauréat","tender","appel d'offres","permit","permis","construction"]):
        persona = "Head of Development + Project Finance"
        gesture = "Mettre en WATCH ou contacter avec prudence : vérifier maturité et besoin financier avant outreach."
    else:
        persona = "Project Finance / Finance"
        gesture = "Ne pas contacter sans preuve supplémentaire ; enrichir financement, portefeuille et persona."

    reasons = []
    if strong_count:
        reasons.append(f"{strong_count} signal(aux) fort(s)")
    if medium_count:
        reasons.append(f"{medium_count} signal(aux) projet/marché")
    reasons.append(f"{n_sources} source(s) publique(s)")
    if status == "INSUFFICIENT":
        reasons.append("preuve insuffisante pour une action commerciale immédiate")

    return {
        "company": company,
        "score": score,
        "status": status,
        "reason": " ; ".join(reasons),
        "persona": persona,
        "gesture": gesture,
        "n_sources": n_sources,
        "strong_count": strong_count,
        "medium_count": medium_count
    }

def log_run(company, result, elapsed_s):
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "company": company,
        "status": result["status"],
        "score": result["score"],
        "sources": result["n_sources"],
        "elapsed_s": round(elapsed_s, 2),
        "direct_api_cost_eur": 0.0,
    }
    df = pd.DataFrame([row])
    try:
        if LOG_FILE.exists():
            old = pd.read_csv(LOG_FILE)
            pd.concat([old, df], ignore_index=True).to_csv(LOG_FILE, index=False)
        else:
            df.to_csv(LOG_FILE, index=False)
    except Exception:
        # Railway peut utiliser un filesystem éphémère : le log n'est pas critique pour la démo.
        pass

def render_result(result, evidence, elapsed):
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Status", result["status"])
    c2.metric("Score", f"{result['score']}/10")
    c3.metric("Temps du run", f"{elapsed:.1f}s")
    c4.metric("Coût API direct", "0 €")

    st.subheader("Pourquoi")
    st.write(result["reason"])
    st.subheader("Persona recommandé")
    st.write(result["persona"])
    st.subheader("Geste commercial recommandé")
    st.write(result["gesture"])

    st.subheader("Preuves publiques")
    if evidence.empty:
        st.warning("Aucune preuve récupérée.")
    else:
        display_cols = ["title","date","strong_signals","medium_signals","persona_evidence","url"]
        st.dataframe(evidence[display_cols], use_container_width=True, hide_index=True)

st.markdown("""
<style>
.block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
[data-testid="stMetric"] {background: #ffffff; border: 1px solid #e7e7e2; padding: 14px 16px; border-radius: 14px;}
div.stButton > button:first-child {border-radius: 10px; font-weight: 700;}
.small-note {color:#6b7280;font-size:0.9rem;}
</style>
""", unsafe_allow_html=True)
st.title("⚡ Nepsis Account Qualifier")
st.caption("Compte → preuves publiques → score explicable → CONTACT / WATCH / INSUFFICIENT → geste recommandé")

tab1, tab2, tab3 = st.tabs(["Qualifier un compte", "Benchmark 20 comptes", "Règles & limites"])

with tab1:
    company = st.text_input("Nom de l’entreprise", placeholder="Ex. Neoen, CVE, Akuo...")
    if st.button("Analyser", type="primary", disabled=not company.strip()):
        with st.spinner("Recherche de signaux publics..."):
            t0 = time.perf_counter()
            try:
                evidence = search_web(company.strip())
                result = score_company(company.strip(), evidence)
                elapsed = time.perf_counter() - t0
                log_run(company.strip(), result, elapsed)
                render_result(result, evidence, elapsed)
            except Exception as e:
                st.error(str(e))

with tab2:
    st.write("Ce benchmark lance exactement le même qualifieur sur 20 comptes réels.")
    if TEST_FILE.exists():
        tests = pd.read_csv(TEST_FILE)
        st.dataframe(tests, use_container_width=True, hide_index=True)
        if st.button("Lancer le benchmark 20 comptes"):
            rows = []
            progress = st.progress(0)
            for i, company_name in enumerate(tests["company"].tolist()):
                t0 = time.perf_counter()
                try:
                    ev = search_web(company_name)
                    res = score_company(company_name, ev)
                    elapsed = time.perf_counter() - t0
                    rows.append({
                        "company": company_name,
                        "status": res["status"],
                        "score": res["score"],
                        "sources": res["n_sources"],
                        "strong_signals": res["strong_count"],
                        "medium_signals": res["medium_count"],
                        "elapsed_s": round(elapsed,2),
                        "direct_api_cost_eur": 0.0,
                        "human_review": "",
                        "review_notes": "",
                    })
                except Exception as e:
                    rows.append({"company": company_name, "status":"ERROR", "score":0, "sources":0,
                                 "strong_signals":0,"medium_signals":0,"elapsed_s":0,
                                 "direct_api_cost_eur":0.0,"human_review":"","review_notes":str(e)})
                progress.progress((i+1)/len(tests))
            out = pd.DataFrame(rows)
            out_path = APP_DIR / "benchmark_results.csv"
            out.to_csv(out_path, index=False)
            st.success(f"Benchmark terminé : {out_path.name}")
            st.dataframe(out, use_container_width=True, hide_index=True)
            st.download_button("Télécharger benchmark_results.csv",
                               data=out.to_csv(index=False).encode("utf-8"),
                               file_name="benchmark_results.csv",
                               mime="text/csv")
    else:
        st.warning("test_accounts.csv manquant.")

with tab3:
    st.markdown("""
### Score /10 — règles explicables
- **Signal / timing : 0–4** — financement, refinancement, M&A, recrutement project finance.
- **Fit EnR : 0–3** — preuves publiques que le compte opère sur solaire/éolien/BESS/EnR.
- **Maturité / activité projet : 0–2** — portefeuille, pipeline, construction, projets.
- **Persona evidence : 0–1** — rôle finance / project finance / investment visible.

### Décision
- **CONTACT** : score ≥8 **et** au moins un signal fort.
- **WATCH** : score 5–7 ou activité projet sans fenêtre commerciale suffisamment forte.
- **INSUFFICIENT** : score <5, moins de 2 sources, ou preuves trop faibles.

### Limites
- La recherche web peut rater une source ou une date.
- Parent/SPV peut rester ambigu.
- Un AO gagné ne prouve pas un besoin d'achat immédiat.
- Le score ne remplace pas une revue humaine : il priorise.
- **Coût API direct : 0 €** car le moteur utilise une recherche web publique sans API payante.
- Le temps/run est mesuré automatiquement.
""")
