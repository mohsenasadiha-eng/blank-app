import streamlit as st
import subprocess, tempfile, zipfile, json, hmac, shutil
from pathlib import Path

st.set_page_config(page_title="StandUp Reels Studio", page_icon="🎤")
st.title("🎤 StandUp Reels Studio")
st.warning("Non caricare video riservati se l’app Streamlit è pubblica. Verifica le impostazioni Sharing.")
if st.button("Cancella sessione"):
    st.session_state.clear()
    st.rerun()

def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def stamp(t):
    ms = max(0, round(t*1000))
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"

@st.cache_resource
def model():
    from faster_whisper import WhisperModel
    return WhisperModel("tiny", device="cpu", compute_type="int8")

st.caption("Trascrizione italiana, proposte di clip, sottotitoli e export verticale. Le proposte non identificano ancora automaticamente le battute.")
u = st.file_uploader("Carica performance", type=["mp4","mov","mkv","webm"])
if u is None:
    st.stop()
if not shutil.which("ffmpeg"):
    st.error("FFmpeg non disponibile")
    st.stop()
import hashlib
data = u.getvalue()
key = hashlib.sha256(data).hexdigest()
if st.session_state.get("video_key") != key:
    for k in list(st.session_state):
        if k != "auth":
            del st.session_state[k]
    st.session_state.video_key = key
if st.button("Analizza performance", type="primary"):
    try:
        with st.spinner("Trascrizione in corso"):
            with tempfile.TemporaryDirectory() as d:
                src = Path(d)/"input"
                src.write_bytes(data)
                duration = float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(src)]))
                parts, _ = model().transcribe(str(src), language="it", word_timestamps=True, vad_filter=True)
                segments = []
                for s in parts:
                    segments.append(dict(start=s.start,end=s.end,text=s.text.strip(),words=[(w.start,w.end,w.word) for w in s.words or []]))
                st.session_state.analysis = (duration,segments)
    except Exception as e:
        st.error(str(e))
if "analysis" not in st.session_state:
    st.stop()
duration, segments = st.session_state.analysis
st.download_button("Trascrizione", "\n".join(f"{s['start']:.1f}: {s['text']}" for s in segments), "trascrizione.txt")
st.subheader("Clip candidate")
picks=[]
i=0
while i<len(segments) and len(picks)<10:
    a=segments[i]["start"]
    j=i+1
    while j<len(segments) and segments[j]["end"]-a<=55:
        j+=1
    b=min(duration,segments[j-1]["end"]+3)
    if b-a>=15:
        picks.append((max(0,a-1),b," ".join(s["text"] for s in segments[i:j])))
    i=j
if not picks:
    picks=[(0,min(duration,60),"Clip manuale")]
chosen=[]
for i,(a,b,t) in enumerate(picks):
    with st.expander(f"Clip {i+1}: {a:.1f}–{b:.1f}s"):
        st.write(t)
        start=st.number_input("Inizio",0.,float(duration),float(a),key=f"a{i}")
        end=st.number_input("Fine",0.,float(duration),float(b),key=f"b{i}")
        hook=st.text_input("Hook / titolo",t[:80],key=f"h{i}")
        if st.checkbox("Esporta",key=f"c{i}"):
            chosen.append((start,end,hook))
resolution=st.selectbox("Risoluzione",["720×1280","1080×1920"])
if st.button("Crea Reel",disabled=not chosen):
    try:
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src=root/"input"
            src.write_bytes(data)
            width,height=map(int,resolution.split("×"))
            bundle=root/"reels.zip"
            with zipfile.ZipFile(bundle,"w") as z:
                for i,(a,b,hook) in enumerate(chosen,1):
                    if not 0<b-a<=90:
                        st.warning(f"Clip {i}: durata non valida")
                        continue
                    lines=[]
                    for s in segments:
                        words=[w for w in s["words"] if w[1]>a and w[0]<b]
                        for k in range(0,len(words),5):
                            g=words[k:k+5]
                            lines.append(f"{len(lines)+1}\n{stamp(max(0,g[0][0]-a))} --> {stamp(min(b,g[-1][1])-a)}\n{''.join(w[2] for w in g).strip()}\n")
                    sub=root/f"reel{i}.srt"
                    sub.write_text("\n".join(lines),encoding="utf-8")
                    out=root/f"reel{i}.mp4"
                    vf=f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
                    if lines:
                        vf+=f",subtitles={sub}:force_style='FontSize=18,Outline=2,MarginV=100'"
                    with st.spinner(f"Montaggio clip {i}"):
                        run(["ffmpeg","-y","-ss",str(a),"-i",str(src),"-t",str(b-a),"-vf",vf,"-c:v","libx264","-preset","veryfast","-threads","2","-c:a","aac","-movflags","+faststart",str(out)])
                    z.write(out,out.name)
                    z.write(sub,sub.name)
                    z.writestr(f"caption{i}.txt",hook+"\nSeguimi per altri pezzi di stand-up!\n#standupcomedy #standupitalia #comicita")
            st.session_state.bundle=bundle.read_bytes()
    except Exception as e:
        st.error(str(e))
if "bundle" in st.session_state:
    st.download_button("Scarica Reel ZIP",st.session_state.bundle,"StandUp_Reels.zip",mime="application/zip")
