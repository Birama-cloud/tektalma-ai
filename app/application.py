"""Interface TEKTALMA AI.  Lancer :  streamlit run app/application.py"""
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from app import voice  # noqa: E402
from app.checklist import LABELS, checklist_html, checklist_pdf, generate_checklist  # noqa: E402
from app.pipeline import Tektalma  # noqa: E402

st.set_page_config(page_title="TEKTALMA AI", page_icon="🇸🇳", layout="centered",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- textes (⚠️ wolof à faire relire)
LANG_OPTIONS = {"Auto": None, "Wolof": "wo", "Français": "fr", "English": "en"}
EXAMPLES = [
    "Carte nationale bi, nan la ma mën a def ngir jël ko ?",
    "Carte nationale bi, dama ko ñàkk, lan la ma wara def ?",
    "Comment obtenir ma carte nationale d'identité ?",
    "Et si je l'ai perdue ?",
    "Combien coûte le passeport ?",
    "D'où viennent ces informations ?",
]
UI = {
    "fiche": {"wo": "📋 Defar sama fiche", "fr": "📋 Générer ma fiche", "en": "📋 Create my checklist"},
    "download": {"wo": "⬇️ Wàcce fiche bi (PDF)", "fr": "⬇️ Télécharger la fiche (PDF)",
                 "en": "⬇️ Download checklist (PDF)"},
    "sources": {"wo": "📚 Fan la xibaar yi jóge", "fr": "📚 Sources officielles", "en": "📚 Official sources"},
    "thinking": {"wo": "Maa ngi seet ci sources officielles yi…", "fr": "Recherche dans les sources officielles…",
                 "en": "Searching official sources…"},
    "fiche_wait": {"wo": "Maa ngi defar fiche bi…", "fr": "Préparation de la fiche…", "en": "Preparing checklist…"},
}


def t(key, lang):
    return UI[key].get(lang or "fr", UI[key]["fr"])


# ---------------------------------------------------------------- design
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=Manrope:wght@400;500;600&display=swap');
:root{
  --night:#0A1430; --deep:#12204A; --ivory:#EEF1F7; --muted:#8E9BBD;
  --line:rgba(160,180,230,.18); --gold:#F2B233; --teranga:#1FB36B; --clay:#E4572E;
}
.stApp{background:
  radial-gradient(900px 500px at 50% -120px, rgba(242,178,51,.14), transparent 70%),
  radial-gradient(700px 600px at 110% 110%, rgba(31,179,107,.10), transparent 70%),
  var(--night); color:var(--ivory);}
html, body, .stApp, p, li, label, input, textarea, button{font-family:Manrope, system-ui, sans-serif !important;}
header[data-testid="stHeader"]{background:transparent;}
#MainMenu, footer, [data-testid="stToolbar"]{visibility:hidden;}
.block-container{padding-top:1.6rem; max-width:760px;}

/* --- orbe vocale : l'élément signature --- */
.tk-hero{display:flex; flex-direction:column; align-items:center; text-align:center; padding:12px 0 6px;}
.tk-orb{position:relative; width:150px; height:150px; margin-bottom:18px;}
.tk-orb span{position:absolute; inset:0; border-radius:50%; border:2px solid;}
.tk-orb span:nth-child(1){border-color:rgba(31,179,107,.55); animation:tk-breathe 4.8s ease-in-out infinite;}
.tk-orb span:nth-child(2){inset:16px; border-color:rgba(242,178,51,.7); animation:tk-breathe 4.8s ease-in-out .5s infinite;}
.tk-orb span:nth-child(3){inset:32px; border-color:rgba(228,87,46,.6); animation:tk-breathe 4.8s ease-in-out 1s infinite;}
.tk-orb .core{position:absolute; inset:46px; border-radius:50%;
  background:radial-gradient(circle at 35% 30%, #FFE7A8, var(--gold) 45%, #B9791A 100%);
  box-shadow:0 0 38px rgba(242,178,51,.55), 0 0 90px rgba(242,178,51,.25);}
@keyframes tk-breathe{0%,100%{transform:scale(1); opacity:.9} 50%{transform:scale(1.06); opacity:.45}}
@media (prefers-reduced-motion: reduce){.tk-orb span{animation:none}}
.tk-word{font-family:Sora, sans-serif; font-weight:700; font-size:2.4rem; letter-spacing:.14em; line-height:1;
  background:linear-gradient(90deg, var(--ivory), #C9D3EE); -webkit-background-clip:text; color:transparent;}
.tk-wo{font-family:Sora, sans-serif; font-size:1.2rem; margin:14px 0 4px; color:var(--gold);}
.tk-fr{color:var(--muted); max-width:520px; margin:0 auto; font-size:.95rem; line-height:1.55;}
.tk-bar{display:flex; align-items:center; gap:12px; padding:4px 0 10px;}
.tk-bar .tk-orb{width:38px; height:38px; margin:0;}
.tk-bar .tk-orb span:nth-child(2){inset:5px} .tk-bar .tk-orb span:nth-child(3){inset:10px}
.tk-bar .tk-orb .core{inset:13px; box-shadow:0 0 14px rgba(242,178,51,.6);}
.tk-bar .tk-word{font-size:1.25rem;}
.tk-bar small{color:var(--muted); display:block; font-size:.8rem;}

/* --- barre de commandes : pastilles cliquables --- */
.st-key-tk_controls{gap:8px !important; margin:8px 0 2px;}
.st-key-tk_lang [role="radiogroup"]{gap:8px; flex-wrap:wrap; justify-content:center;}
.st-key-tk_lang button[data-variant="segmented_control"],
.st-key-tk_voice_on button, .st-key-tk_voice_off button, .st-key-tk_new button{
  border-radius:999px !important; border:1px solid var(--line) !important; margin:0 !important;
  background:rgba(238,241,247,.04) !important; color:var(--ivory) !important;
  padding:6px 16px !important; min-height:36px; transition:border-color .15s, background .15s;}
.st-key-tk_lang button[data-variant="segmented_control"] p,
.st-key-tk_controls .stButton button p{color:inherit !important; font-weight:600; font-size:.88rem;}
.st-key-tk_lang button[data-variant="segmented_control"]:hover,
.st-key-tk_controls .stButton button:hover{border-color:var(--gold) !important; color:var(--gold) !important;}
.st-key-tk_lang button[aria-checked="true"]{background:var(--gold) !important; border-color:var(--gold) !important;
  color:#1B2235 !important;}
.st-key-tk_lang button[aria-checked="true"]:hover{color:#1B2235 !important; background:#FFD36E !important;}
.st-key-tk_voice_on button{border-color:rgba(31,179,107,.6) !important; background:rgba(31,179,107,.12) !important;
  color:#8FE3B6 !important;}
.st-key-tk_voice_off button{color:var(--muted) !important; border-style:dashed !important;}
.st-key-tk_controls button:focus-visible{outline:2px solid var(--gold) !important; outline-offset:2px;}
@media (max-width:520px){
  .st-key-tk_controls, .st-key-tk_lang [role="radiogroup"]{gap:6px !important;}
  .st-key-tk_lang button[data-variant="segmented_control"],
  .st-key-tk_controls .stButton button{padding:4px 11px !important; min-height:32px;}
  .st-key-tk_lang button[data-variant="segmented_control"] p,
  .st-key-tk_controls .stButton button p{font-size:.8rem;}
}

/* --- validation du vocal : envoyer / annuler --- */
.st-key-tk_review{gap:10px !important; margin:-4px 0 6px;}
.st-key-tk_send button, .st-key-tk_cancel button{border-radius:999px !important; padding:8px 20px !important;
  min-height:40px; font-weight:600;}
.st-key-tk_send button{background:var(--gold) !important; color:#1B2235 !important; border:1px solid var(--gold) !important;}
.st-key-tk_send button:hover{background:#FFD36E !important; color:#1B2235 !important;}
.st-key-tk_cancel button{background:transparent !important; color:#F3A58E !important;
  border:1px solid rgba(228,87,46,.6) !important;}
.st-key-tk_cancel button:hover{background:rgba(228,87,46,.12) !important; color:#FFC2B0 !important;}
.st-key-tk_send button p, .st-key-tk_cancel button p{color:inherit !important; font-weight:600;}
/* vocal enregistré : un seul grand bouton (lecture), « Annuler » sert à recommencer */
[data-testid="stAudioInput"] div:has(> span > [aria-label="Play"]) > span:has(> [aria-label="Record"]),
[data-testid="stAudioInput"] div:has(> span > [aria-label="Pause"]) > span:has(> [aria-label="Record"]){display:none !important;}
[data-testid="stAudioInput"] [data-testid="stElementToolbar"]{display:none !important;}
/* micro désactivé pendant qu'une réponse est en cours */
[data-testid="stAudioInput"] span:has(> :disabled)::before,
[data-testid="stAudioInput"] span:has(> :disabled)::after{opacity:.25;}
[data-testid="stAudioInputActionButton"]:disabled{opacity:.4; filter:grayscale(.6); cursor:not-allowed;
  animation:none !important; transform:none !important;}

/* --- micro : grand bouton rond centré (même composant Streamlit, seul le style change) --- */
[data-testid="stAudioInput"]{display:flex; flex-direction:column; align-items:center; margin:18px 0 8px;}
[data-testid="stAudioInput"] > label{justify-content:center; width:100%; margin-bottom:6px;}
[data-testid="stAudioInput"] > label p{font-family:Sora, sans-serif !important; color:var(--muted);
  font-size:.9rem; text-align:center;}
[data-testid="stAudioInput"] > div:last-child{display:flex; flex-direction:column; align-items:center;
  gap:4px; background:transparent !important; border:none !important; box-shadow:none !important;
  height:auto !important; width:100%; padding:8px 0 !important;}
/* la zone du bouton + barres sonores de chaque côté */
[data-testid="stAudioInput"] span:has(> [data-testid="stAudioInputActionButton"]){
  position:relative; display:flex; align-items:center; justify-content:center;
  width:150px; height:150px; margin:0 !important;}
[data-testid="stAudioInput"] span:has(> [data-testid="stAudioInputActionButton"])::before,
[data-testid="stAudioInput"] span:has(> [data-testid="stAudioInputActionButton"])::after{
  content:""; position:absolute; top:50%; width:64px; height:96px; margin-top:-48px;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='64' height='96' viewBox='0 0 64 96'><g fill='%23F2B233'><rect x='0' y='36' width='8' height='24' rx='4' opacity='.55'/><rect x='18' y='20' width='8' height='56' rx='4' opacity='.75'/><rect x='36' y='0' width='8' height='96' rx='4'/><rect x='54' y='26' width='8' height='44' rx='4' opacity='.8'/></g></svg>") no-repeat center/contain; transition:opacity .3s; pointer-events:none;}
[data-testid="stAudioInput"] span:has(> [data-testid="stAudioInputActionButton"])::before{right:calc(100% + 18px); transform:scaleX(-1);}
[data-testid="stAudioInput"] span:has(> [data-testid="stAudioInputActionButton"])::after{left:calc(100% + 18px);}
/* le bouton lui-même : cœur bleu nuit, anneau doré lumineux */
[data-testid="stAudioInputActionButton"]{width:132px !important; height:132px !important; min-height:132px;
  min-width:132px !important; max-width:none !important; flex:0 0 132px !important; aspect-ratio:1/1;
  border-radius:50% !important; padding:0 !important; color:#F4F7FF !important; cursor:pointer;
  background:radial-gradient(circle at 50% 35%, #2F63E0 0%, #173A9C 45%, #0B1A4A 100%) !important;
  border:4px solid var(--gold) !important;
  box-shadow:0 0 0 10px rgba(242,178,51,.10), 0 0 34px rgba(242,178,51,.45), inset 0 0 26px rgba(0,0,0,.35);
  transition:transform .2s ease, box-shadow .2s ease;}
[data-testid="stAudioInputActionButton"] svg{width:68px !important; height:68px !important;}
[data-testid="stAudioInputActionButton"]:hover{transform:scale(1.04);
  box-shadow:0 0 0 12px rgba(242,178,51,.14), 0 0 46px rgba(242,178,51,.6), inset 0 0 26px rgba(0,0,0,.35);}
[data-testid="stAudioInputActionButton"]:focus-visible{outline:3px solid #FFE7A8; outline-offset:6px;}
/* pendant l'enregistrement : anneau rouge qui pulse, barres qui bougent */
[data-testid="stAudioInputActionButton"][aria-label="Stop recording"]{border-color:var(--clay) !important;
  animation:tk-rec 1.4s ease-in-out infinite;}
@keyframes tk-rec{0%,100%{box-shadow:0 0 0 8px rgba(228,87,46,.18), 0 0 30px rgba(228,87,46,.45)}
  50%{box-shadow:0 0 0 20px rgba(228,87,46,.05), 0 0 60px rgba(228,87,46,.7)}}
[data-testid="stAudioInput"] span:has(> [aria-label="Stop recording"])::before,
[data-testid="stAudioInput"] span:has(> [aria-label="Stop recording"])::after{animation:tk-bars .9s ease-in-out infinite;}
[data-testid="stAudioInput"] span:has(> [aria-label="Stop recording"])::before{animation-name:tk-bars-l;}
@keyframes tk-bars{0%,100%{transform:scaleY(.7)} 50%{transform:scaleY(1.15)}}
@keyframes tk-bars-l{0%,100%{transform:scaleX(-1) scaleY(.7)} 50%{transform:scaleX(-1) scaleY(1.15)}}
@media (prefers-reduced-motion: reduce){
  [data-testid="stAudioInputActionButton"], [data-testid="stAudioInput"] span::before,
  [data-testid="stAudioInput"] span::after{animation:none !important;}}
/* onde et minuteur : discrets, sous le bouton */
[data-testid="stAudioInput"] > div:last-child > div:has([data-testid="stAudioInputWaveSurfer"]){
  width:min(320px, 80%); min-height:28px; opacity:.85;}
[data-testid="stAudioInputWaveformTimeCode"]{color:var(--muted); font-size:.8rem; margin:0 !important;
  background:transparent !important;}
@media (max-width:520px){
  [data-testid="stAudioInput"] span:has(> [data-testid="stAudioInputActionButton"])::before,
  [data-testid="stAudioInput"] span:has(> [data-testid="stAudioInputActionButton"])::after{width:44px; height:66px; margin-top:-33px;}
}

/* --- conversation --- */
[data-testid="stChatMessage"]{background:rgba(18,32,74,.55); border:1px solid var(--line);
  border-radius:4px 18px 18px 18px; padding:14px 16px; margin-bottom:10px;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){
  background:rgba(242,178,51,.08); border-color:rgba(242,178,51,.3); border-radius:18px 4px 18px 18px;}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li{color:var(--ivory); line-height:1.6;}
[data-testid="stExpander"]{border:1px solid rgba(31,179,107,.35); border-radius:12px; background:rgba(31,179,107,.05);}
[data-testid="stExpander"] summary p{color:var(--teranga) !important; font-weight:600;}
[data-testid="stExpander"] a{color:#6FE0A4;}

/* --- boutons --- */
.stButton button, .stDownloadButton button{border-radius:999px; border:1px solid var(--line);
  background:rgba(238,241,247,.04); color:var(--ivory); font-weight:600;}
.stButton button:hover, .stDownloadButton button:hover{border-color:var(--gold); color:var(--gold);}
.stButton button:focus-visible, .stDownloadButton button:focus-visible{outline:2px solid var(--gold); outline-offset:2px;}
.stDownloadButton button{background:var(--gold); color:#1B2235; border:none;}
.stDownloadButton button:hover{background:#FFD36E; color:#1B2235;}
/* --- zone de saisie : fond sombre, texte clair --- */
[data-testid="stBottom"], [data-testid="stBottom"] > div{background:var(--night) !important;}
[data-testid="stChatInput"]{border-radius:18px; background:var(--deep) !important;
  border:1px solid rgba(242,178,51,.45) !important;}
[data-testid="stChatInput"] > div{background:transparent !important;}
[data-testid="stChatInput"] textarea{color:var(--ivory) !important; -webkit-text-fill-color:var(--ivory) !important;
  background:transparent !important; caret-color:var(--gold);}
[data-testid="stChatInput"] textarea::placeholder{color:var(--muted) !important;
  -webkit-text-fill-color:var(--muted) !important; opacity:1;}
[data-testid="stChatInput"] button{color:var(--gold) !important;}

/* --- fiche : aspect document officiel imprimé --- */
.tk-fiche{background:#FBF8F1; color:#1B2235; border-radius:3px; padding:0 22px 18px; margin:6px 0 10px;
  box-shadow:0 10px 30px rgba(0,0,0,.35);}
.tk-fiche .flag{height:6px; margin:0 -22px 16px;
  background:linear-gradient(90deg,#00853F 33.3%,#FDEF42 33.3% 66.6%,#E31B23 66.6%);}
.tk-fiche h3{font-family:Sora, sans-serif; font-size:1.15rem; margin:0 0 4px; color:#1B2235;}
.tk-fiche h4{font-family:Sora, sans-serif; font-size:.9rem; margin:14px 0 6px; color:#00853F;
  border-bottom:1px solid #D8D2C2; padding-bottom:4px;}
.tk-fiche p, .tk-fiche li{color:#1B2235 !important; font-size:.92rem; margin:3px 0;}
.tk-fiche ul{list-style:none; padding:0; margin:0;}
.tk-fiche li::before{content:""; display:inline-block; width:11px; height:11px; border:1.5px solid #1B2235;
  margin-right:9px; vertical-align:-1px;}
.tk-fiche .facts{display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;}
.tk-fiche .fact{border:1.5px solid #1B2235; padding:6px 10px; font-size:.85rem;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

ORB = "<div class='tk-orb'><span></span><span></span><span></span><div class='core'></div></div>"


@st.cache_resource(show_spinner="TEKTALMA AI mi ngi tàmbali… · Démarrage…")
def get_engine():
    return Tektalma()


engine = get_engine()
state = st.session_state
for key, default in {"messages": [], "last_audio": None, "pending": None, "mic_key": 0}.items():
    state.setdefault(key, default)

# ---------------------------------------------------------------- en-tête
if not state.messages:
    st.markdown(f"""<div class="tk-hero">{ORB}<div class="tk-word">TEKTALMA</div>
      <p class="tk-wo">Na nga def ? Waxal sa laaj, ma tontu la.</p>
      <p class="tk-fr">Carte d'identité, passeport, état civil : posez votre question à voix haute
      ou par écrit, en wolof, en français ou en anglais. Les réponses viennent des sites officiels de l'État.</p>
      </div>""", unsafe_allow_html=True)
else:
    st.markdown(f"""<div class="tk-bar">{ORB}<div><div class="tk-word">TEKTALMA</div>
      <small>Démarches administratives du Sénégal</small></div></div>""", unsafe_allow_html=True)

# ---------------------------------------------------------------- barre de commandes en pastilles
state.setdefault("voice_on", True)


def _toggle_voice():
    state.voice_on = not state.voice_on


def _new_chat():
    state.messages, state.last_audio = [], None


with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center",
                  gap="small", key="tk_controls"):
    choice = st.segmented_control("Làkk · Langue de réponse", list(LANG_OPTIONS), default="Auto",
                                  required=True, label_visibility="collapsed", key="tk_lang")
    st.button("🔊 Voix" if state.voice_on else "🔇 Muet", on_click=_toggle_voice,
              key="tk_voice_on" if state.voice_on else "tk_voice_off",
              help="Lire les réponses à voix haute")
    st.button("↺ Bu bees", key="tk_new", on_click=_new_chat, help="Nouvelle conversation")
forced_lang = LANG_OPTIONS.get(choice or "Auto")
voice_on = state.voice_on


# ---------------------------------------------------------------- rendu des messages
def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "demarche"


def render_fiche(f, lang):
    L = LABELS.get(lang, LABELS["fr"])

    def lst(key):
        items = f.get(key) or []
        return f"<h4>{L[key]}</h4><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>" if items else ""

    facts = "".join(f"<div class='fact'><b>{L[k]}</b> : {f[k]}</div>" for k in ("cout", "delai") if f.get(k))
    st.markdown(f"""<div class="tk-fiche"><div class="flag"></div><h3>{f['titre']}</h3>
      <p>{f['resume']}</p><div class="facts">{facts}</div>
      {lst('documents')}{lst('etapes')}{lst('lieux')}{lst('conseils')}</div>""", unsafe_allow_html=True)


for i, m in enumerate(state.messages):
    with st.chat_message(m["role"], avatar="🧑🏾" if m["role"] == "user" else "🟡"):
        st.markdown(m["content"])
        if m["role"] != "assistant":
            continue
        lang = m.get("lang", "fr")
        if m.get("cached"):
            st.caption("⚡ Tontu bu gaaw · Réponse instantanée")
        if m.get("audio"):
            st.audio(m["audio"], format=m.get("mime", "audio/wav"), autoplay=not m.get("played"))
            m["played"] = True  # lecture automatique une seule fois
        if m.get("sources"):
            with st.expander(t("sources", lang)):
                for s in m["sources"]:
                    maj = s["updated_at"] or "non indiquée"
                    st.markdown(f"**[S{s['n']}] {s['title']}**  \n{s['organisme']}  \n"
                                f"[{s['url']}]({s['url']})  \n:grey[Collectée le {s['collected_at']} · "
                                f"mise à jour : {maj}]")
        if m.get("kind") == "answer" and m.get("docs"):
            if m.get("fiche"):
                render_fiche(m["fiche"], lang)
                if m.get("fiche_pdf"):
                    st.download_button(t("download", lang), data=m["fiche_pdf"],
                                       file_name=f"tektalma-{slug(m['fiche']['titre'])}.pdf",
                                       mime="application/pdf", key=f"dl_{i}")
                else:  # secours si le PDF n'a pas pu être créé
                    st.download_button(t("download", lang), data=m["fiche_html"],
                                       file_name=f"tektalma-{slug(m['fiche']['titre'])}.html",
                                       mime="text/html", key=f"dl_{i}")
            elif st.button(t("fiche", lang), key=f"fiche_{i}"):
                with st.spinner(t("fiche_wait", lang)):
                    try:
                        fiche = generate_checklist(engine.llm, m["docs"], m["question_fr"], lang)
                        m["fiche"] = fiche
                        m["fiche_html"] = checklist_html(fiche, m["sources"], lang)
                        try:
                            m["fiche_pdf"] = checklist_pdf(fiche, m["sources"], lang)
                        except Exception:  # noqa: BLE001
                            m["fiche_pdf"] = None
                    except Exception:  # noqa: BLE001
                        st.warning("Fiche indisponible pour le moment, réessayez dans un instant.")
                st.rerun()

# ---------------------------------------------------------------- entrées : voix + texte
# ---------------------------------------------------------------- entrées : voix (avec validation) + texte
# Une seule question traitée à la fois : tant qu'une réponse est en cours ("job"),
# le micro, les exemples et le chat sont désactivés.
state.setdefault("job", None)            # question en cours de traitement
state.setdefault("pending_audio", None)  # vocal enregistré, en attente de validation


def _queue_text(q):
    if q and q.strip() and state.job is None:
        state.job = {"text": q.strip()}


def _on_chat():
    _queue_text(state.get("tk_chat"))


def _send_audio():
    if state.pending_audio and state.job is None:
        state.job = {"audio": state.pending_audio}
    state.pending_audio = None
    state.mic_key += 1        # vide le micro


def _cancel_audio():
    state.pending_audio = None
    state.mic_key += 1        # supprime le vocal, micro prêt pour un nouvel essai


busy = state.job is not None

audio = st.audio_input("🎙️ Bësal, wax, bësaat · Appuyez, parlez, appuyez à nouveau",
                       key=f"mic_{state.mic_key}", disabled=busy)
if not busy:
    if audio is not None:
        audio_bytes = audio.getvalue()
        digest = hashlib.md5(audio_bytes).hexdigest()
        if digest != state.last_audio:          # nouveau vocal : on attend la validation
            state.last_audio = digest
            state.pending_audio = (audio_bytes, audio.type or "audio/wav")
    else:
        state.pending_audio = None              # vocal effacé depuis le micro
    if state.pending_audio:
        with st.container(horizontal=True, horizontal_alignment="center", gap="small", key="tk_review"):
            st.button("✅ Yónnee · Envoyer", key="tk_send", on_click=_send_audio)
            st.button("✖ Dindi · Annuler", key="tk_cancel", on_click=_cancel_audio)
if state.get("notice"):
    st.warning(state.pop("notice"))

with st.expander("💡 Misaal · Exemples de questions"):
    cols = st.columns(2)
    for k, ex in enumerate(EXAMPLES):
        cols[k % 2].button(ex, key=f"ex_{k}", use_container_width=True,
                           on_click=_queue_text, args=(ex,), disabled=busy)
st.chat_input("Bindal sa laaj… · Écrivez votre question…", key="tk_chat",
              on_submit=_on_chat, disabled=busy)

# ---------------------------------------------------------------- traitement (une question à la fois)
if state.job:
    job = state.job
    try:
        history = [{"role": m["role"], "content": m["content"], "sources": m.get("sources")}
                   for m in state.messages]
        with st.spinner(t("thinking", forced_lang)):
            if "audio" in job:   # un seul appel : écoute + compréhension
                ans = engine.ask(None, history, force_lang=forced_lang,
                                 audio=job["audio"][0], mime_type=job["audio"][1])
            else:
                ans = engine.ask(job["text"], history, force_lang=forced_lang)
            audio_out, mime = (voice.speak(engine.llm, ans.text, ans.language)
                               if voice_on and ans.kind != "error" else (None, None))
        state.messages.append({"role": "user", "content": ans.question or job.get("text") or "🎙️"})
        state.messages.append({
            "role": "assistant", "content": ans.text, "kind": ans.kind, "lang": ans.language,
            "sources": ans.sources, "docs": ans.docs, "question_fr": ans.question_fr,
            "audio": audio_out, "mime": mime, "played": False,
            "cached": bool(ans.debug.get("cache")),
        })
    finally:
        state.job = None          # le micro et le chat sont réactivés
    st.rerun()
