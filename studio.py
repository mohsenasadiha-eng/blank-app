
import streamlit as st
import subprocess, tempfile, json, re, shutil, zipfile, os, textwrap, uuid
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).parent
if "workspace_id" not in st.session_state:
    st.session_state["workspace_id"] = uuid.uuid4().hex
WORK = Path(tempfile.gettempdir()) / f"standup_reels_{st.session_state['workspace_id']}"
WORK.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="StandUp Reels Studio", page_icon="🎤", layout="wide")
st.markdown("""
<style>
.stApp {background:#101116;color:#f4f4f5}
section[data-testid="stSidebar"] {background:#171922}
div[data-testid="stMetric"] {background:#1c202b;padding:14px;border-radius:12px}
.stButton>button {border-radius:10px;font-weight:700}
.hero {padding:28px;border:1px solid #343846;border-radius:18px;background:linear-gradient(120deg,#1d2030,#292035)}
.small {color:#a8adbb}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🎤 StandUp Reels Studio</h1><p>Il tuo studio privato online per trasformare gli spettacoli in Reels. I file vengono elaborati temporaneamente sul server.</p><p class="small">Analisi completa · Trascrizione italiana · Selezione clip · Sottotitoli · Montaggio verticale · Pacchetto Instagram</p></div>', unsafe_allow_html=True)

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout)[-4000:])
    return p.stdout.strip()

def has_ffmpeg():
    return shutil.which("ffmpeg") and shutil.which("ffprobe")

def probe(path):
    raw = run(["ffprobe","-v","error","-show_entries","format=duration:stream=width,height","-of","json",str(path)])
    data=json.loads(raw)
    dur=float(data["format"]["duration"])
    v=next((x for x in data.get("streams",[]) if "width" in x),{})
    return dur, int(v.get("width",0)), int(v.get("height",0))

def fmt(t):
    ms=int(max(0,t)*1000)
    h=ms//3600000; ms%=3600000
    m=ms//60000; ms%=60000
    s=ms//1000; ms%=1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def srt_escape(s):
    return s.replace("{","(").replace("}",")")

def write_srt(words, start, end, out):
    # Chunk transcript words into short mobile-friendly subtitle cards.
    selected=[w for w in words if w["end"]>start and w["start"]<end]
    lines=[]
    chunk=[]
    for w in selected:
        token=w["word"].strip()
        if not token: continue
        chunk.append(w)
        txt=" ".join(x["word"].strip() for x in chunk)
        if len(txt)>38 or len(chunk)>=6 or re.search(r"[.!?…]$",token):
            a=max(start,chunk[0]["start"]); b=min(end,chunk[-1]["end"])
            lines.append((a,b,txt)); chunk=[]
    if chunk:
        lines.append((max(start,chunk[0]["start"]),min(end,chunk[-1]["end"])," ".join(x["word"].strip() for x in chunk)))
    with open(out,"w",encoding="utf-8") as f:
        for i,(a,b,txt) in enumerate(lines,1):
            f.write(f"{i}\n{fmt(a-start)} --> {fmt(max(a-start+0.25,b-start))}\n{srt_escape(txt)}\n\n")

def transcribe(path, model_size):
    from faster_whisper import WhisperModel
    model=WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info=model.transcribe(str(path), language="it", word_timestamps=True, vad_filter=True)
    segs=[]; words=[]
    for seg in segments:
        segs.append({"start":seg.start,"end":seg.end,"text":seg.text.strip()})
        if seg.words:
            for w in seg.words:
                words.append({"start":w.start,"end":w.end,"word":w.word})
    return segs, words, info

def propose(segs, duration, min_len, max_len):
    # Transparent baseline candidate finder: groups transcript segments into self-contained windows.
    # It does not claim to understand joke quality; user reviews all candidates.
    candidates=[]
    i=0
    while i<len(segs):
        start=segs[i]["start"]
        j=i
        while j<len(segs) and segs[j]["end"]-start < max_len:
            j+=1
        if j==i: j+=1
        end=segs[j-1]["end"]
        if min_len <= end-start <= max_len:
            text=" ".join(x["text"] for x in segs[i:j])
            candidates.append({"start":max(0,start-1.5),"end":min(duration,end+1.5),"text":text})
        i=max(i+1,j-1)
    # add a few windows where audience laughter/energy can be reviewed manually
    return candidates

def render_clip(src, start, end, out, srt=None):
    duration=end-start
    vf="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    if srt:
        escaped=str(srt).replace("\\","/").replace(":","\\:")
        vf += f",subtitles='{escaped}':force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=250'"
    cmd=["ffmpeg","-y","-ss",str(start),"-i",str(src),"-t",str(duration),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-b:a","192k","-movflags","+faststart",str(out)]
    run(cmd)

with st.sidebar:
    st.header("Impostazioni")
    model_size=st.selectbox("Modello di trascrizione",["tiny","base","small"],index=0,help="tiny è consigliato per l’hosting gratuito. base/small possono essere lenti o superare la memoria disponibile.")
    min_len=st.slider("Durata minima clip (secondi)",15,40,20)
    max_len=st.slider("Durata massima clip (secondi)",40,90,60)
    st.caption("Hosting gratuito: CPU e memoria limitate. Il modello viene scaricato sul server al primo utilizzo; i tempi dipendono dalla durata del video.")

if not has_ffmpeg():
    st.error("FFmpeg non è disponibile sul server. Controlla che packages.txt sia stato incluso nel repository e riavvia il deploy.")
    st.stop()

st.caption("Limite upload configurato: 200 MB per file. Per registrazioni più pesanti, comprimi prima il video o dividilo in parti.")
uploaded=st.file_uploader("Carica la registrazione integrale",type=["mp4","mov","mkv","webm","m4v"])
if uploaded:
    source=WORK / Path(uploaded.name).name
    source.write_bytes(uploaded.getbuffer())
    try:
        duration,width,height=probe(source)
        st.success(f"Video caricato: {uploaded.name}")
        c1,c2,c3=st.columns(3)
        c1.metric("Durata",f"{duration/60:.1f} min")
        c2.metric("Risoluzione",f"{width} × {height}")
        c3.metric("Modalità","Sessione privata")
    except Exception as e:
        st.error(f"Impossibile leggere il video: {e}")
        st.stop()

    if st.button("🚀 Analizza tutta la performance",type="primary",use_container_width=True):
        with st.spinner("Estrazione audio e trascrizione dell'intera registrazione. Può richiedere tempo..."):
            audio=WORK/"audio.wav"
            try:
                run(["ffmpeg","-y","-i",str(source),"-vn","-ac","1","-ar","16000",str(audio)])
                segs,words,info=transcribe(audio,model_size)
                st.session_state["source"]=str(source)
                st.session_state["duration"]=duration
                st.session_state["segments"]=segs
                st.session_state["words"]=words
                st.session_state["candidates"]=propose(segs,duration,min_len,max_len)
                st.session_state["transcript"]="\n".join(f'[{x["start"]:.1f}s–{x["end"]:.1f}s] {x["text"]}' for x in segs)
            except Exception as e:
                st.error(f"Analisi non completata: {e}")
                st.info("Verifica la connessione per il primo download del modello e lo spazio libero sul disco.")

if "segments" in st.session_state:
    st.divider()
    st.subheader("1 · Analisi e trascrizione")
    st.caption("La trascrizione copre tutto il video. Le finestre proposte non sono una valutazione AI della comicità: ascolta i passaggi e verifica contesto, risate e punchline.")
    with st.expander("Apri trascrizione integrale",expanded=False):
        st.text_area("Trascrizione con timestamp",st.session_state["transcript"],height=260)
    candidates=st.session_state["candidates"]
    st.subheader(f"2 · Selezione dei momenti ({len(candidates)} proposte)")
    st.write("Rivedi il testo, modifica inizio/fine e scegli i segmenti che hanno contesto, build-up e punchline completi.")
    if not candidates:
        st.warning("Non sono state trovate finestre della durata scelta. Prova a modificare la durata minima/massima o usa i timestamp manuali.")
    chosen=[]
    for idx,c in enumerate(candidates):
        with st.expander(f"Clip candidata {idx+1:02} · {c['start']:.1f}s – {c['end']:.1f}s",expanded=(idx==0)):
            st.write(c["text"])
            a,b=st.columns(2)
            start=a.number_input("Inizio (secondi)",min_value=0.0,max_value=float(st.session_state["duration"]),value=float(c["start"]),step=0.5,key=f"s{idx}")
            end=b.number_input("Fine (secondi)",min_value=0.0,max_value=float(st.session_state["duration"]),value=float(c["end"]),step=0.5,key=f"e{idx}")
            hook=st.text_input("Hook / frase iniziale (solo parole realmente pronunciate)",value=(c["text"][:90]),key=f"h{idx}")
            title=st.text_input("Titolo Reel",value=f"Stand-up clip {idx+1}",key=f"t{idx}")
            if st.checkbox("Seleziona per il montaggio",value=False,key=f"c{idx}"):
                chosen.append({"n":idx+1,"start":start,"end":end,"hook":hook,"title":title,"text":c["text"]})
    st.subheader("3 · Montaggio ed esportazione")
    st.caption("Formato 9:16, 1080×1920, MP4 H.264/AAC. Il crop centrale è automatico: controlla che il volto resti nell'inquadratura. I sottotitoli vanno riletti.")
    if st.button("🎬 Monta i Reel selezionati",type="primary",disabled=(len(chosen)==0),use_container_width=True):
        outdir=WORK/"exports"; outdir.mkdir(exist_ok=True)
        manifest=[]
        progress=st.progress(0)
        for k,item in enumerate(chosen):
            if item["end"]<=item["start"]:
                st.warning(f"Clip {item['n']}: intervallo non valido, saltata.")
                continue
            name=f"REEL_{len(manifest)+1:02}_{re.sub('[^a-zA-Z0-9]+','_',item['title']).strip('_')[:35]}.mp4"
            srt=outdir/(Path(name).stem+".srt")
            mp4=outdir/name
            write_srt(st.session_state["words"],item["start"],item["end"],srt)
            try:
                render_clip(Path(st.session_state["source"]),item["start"],item["end"],mp4,srt)
                manifest.append({**item,"file":name,"duration":round(item["end"]-item["start"],1),"srt":srt.name})
            except Exception as e:
                st.error(f"Errore nel render di {name}: {e}")
            progress.progress((k+1)/len(chosen))
        # Package editorial metadata
        pack=[]
        for i,m in enumerate(manifest,1):
            pack.append(f"""## REEL {i:02}
- File: {m['file']}
- Timestamp originali: {m['start']:.1f}s – {m['end']:.1f}s
- Durata: {m['duration']} secondi
- Hook: {m['hook']}
- Titolo suggerito: {m['title']}
- Cover text: {m['title'][:32]}
- Caption: Una cosa è certa: dal vivo certe situazioni fanno ancora più ridere 😂 Tu cosa avresti fatto? Scrivimelo nei commenti.
- Hashtag: #standupcomedy #comicita #standupitalia #risate #comedyreels #umorismo #italiancomedy
- CTA: Seguimi per altri pezzi di stand-up e condividilo con chi capirebbe questa battuta.
- Sottotitoli: {m['srt']} (da verificare)
""")
        (outdir/"PACCHETTO_INSTAGRAM.md").write_text("\n".join(pack),encoding="utf-8")
        zip_path=WORK/"StandUp_Reels_Export.zip"
        with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
            for p in outdir.iterdir():
                if p.is_file(): z.write(p,p.name)
        st.session_state["export_zip"]=str(zip_path)
        st.session_state["manifest"]=manifest
        st.success(f"Esportazione completata: {len(manifest)} Reel creati.")
    if st.session_state.get("manifest"):
        st.subheader("4 · Controllo qualità e consegna")
        for m in st.session_state["manifest"]:
            st.write(f"**{m['file']}** · {m['duration']}s · {m['start']:.1f}–{m['end']:.1f}s")
            st.caption("Controlla manualmente: hook nei primi 1–2 secondi, punchline completa, risate conservate, sincronizzazione sottotitoli, volto centrato e safe zone Instagram.")
        z=Path(st.session_state["export_zip"])
        st.download_button("⬇️ Scarica ZIP con Reel, sottotitoli e pacchetto Instagram",z.read_bytes(),file_name=z.name,mime="application/zip",use_container_width=True)

st.divider()
st.subheader("Workflow completo · 12 specifiche")
st.markdown("""
1. Ruolo editoriale: analisi orientata alla comicità e alla retention.
2. Analisi integrale: trascrizione dell'intera traccia audio.
3. Selezione: proposte di clip da valutare, non classifiche automatiche di comicità.
4. Hook: suggerimento basato sul testo originale, modificabile.
5. Editing: verticale 9:16, H.264, audio AAC.
6. Sottotitoli: italiano, sincronizzati tramite word timestamps.
7. Durata: finestre configurabili, target 20–60 secondi.
8. Strategia: varietà e qualità richiedono revisione editoriale.
9. Packaging: titolo, caption, cover, hashtag e CTA.
10. QC: checklist prima della pubblicazione.
11. Workflow: sessione web privata e file temporanei sul server.
12. Consegna: MP4, SRT e ZIP.
""")
st.info("Limiti della versione gratuita online: non usa ancora un modello AI per giudicare la comicità, non rileva risate o volti per zoom/reframing intelligenti, non fa color grading avanzato e non pubblica direttamente su Instagram. Ogni video viene caricato sul server per l’elaborazione; lo spazio gratuito può riavviarsi e cancellare i file temporanei. Scarica subito gli export.")
