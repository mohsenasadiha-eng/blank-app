# StandUp Reels Studio — Online privata (free tier)

App Streamlit per trascrivere registrazioni, proporre finestre candidate, montare clip verticali e preparare il pacchetto Instagram.

## Deploy gratuito e privato

Questa versione è predisposta per **Streamlit Community Cloud** con repository GitHub privato.

1. Crea un account GitHub e un nuovo repository impostandolo su **Private**.
2. Carica nel repository tutti i file e le cartelle di questo progetto, mantenendo la struttura.
3. Accedi a https://share.streamlit.io/ con lo stesso account GitHub.
4. Seleziona **Create app** e scegli il repository privato appena creato.
5. Imposta il percorso del file principale su `app/studio.py`.
6. Avvia il deploy e attendi l'installazione di `requirements.txt` e `packages.txt`.
7. In **App settings → Sharing**, verifica che l'accesso sia limitato a **Only specific people**. Non rendere pubblico il repository o l'app.
8. Apri l'URL `*.streamlit.app` generato e accedi con l'account autorizzato.

La documentazione ufficiale spiega il deploy e le impostazioni di privacy: https://docs.streamlit.io/deploy/streamlit-community-cloud

## Privacy e trattamento dei video

- Il codice sorgente rimane nel repository GitHub privato.
- L'app è pensata per essere privata sul piano Streamlit Community Cloud: solo sviluppatori e spettatori invitati possono accedervi.
- **Attenzione:** quando carichi un video, il file viene trasferito al server Streamlit per essere trascritto e montato. Non resta soltanto sul tuo telefono/PC.
- Il progetto usa una cartella temporanea distinta per sessione. Il filesystem del piano gratuito è effimero: un riavvio, uno sleep o un nuovo deploy può cancellare i file. Scarica subito i risultati.
- Non caricare video di altre persone senza averne i diritti e i consensi necessari.

## Limiti del piano gratuito

- Upload configurato a 200 MB per file.
- CPU/RAM e tempi di esecuzione limitati: per questo il modello predefinito è `tiny`.
- Video lunghi o pesanti possono fallire per memoria o timeout. Se necessario, comprimi o dividi la registrazione.
- Il servizio gratuito può andare in sleep e impiegare tempo a riattivarsi.
- Non è un servizio di produzione con disponibilità garantita.

## Funzioni presenti

- Upload video MP4/MOV/MKV/WEBM/M4V.
- Estrazione audio con FFmpeg.
- Trascrizione italiana con faster-whisper e timestamp delle parole.
- Proposte di finestre candidate configurabili.
- Modifica di inizio/fine, hook e titolo; selezione delle clip.
- Export verticale 9:16 1080×1920, MP4 H.264/AAC e sottotitoli SRT.
- Caption, hashtag, CTA e pacchetto ZIP.

## Limiti funzionali dichiarati

Le proposte di clip sono basate su segmenti temporali della trascrizione, non su una comprensione semantica affidabile della battuta. Non è ancora implementato il riconoscimento automatico della risata, la valutazione della punchline, il face tracking, lo zoom intelligente, il color grading avanzato, un controllo qualità automatico completo o la pubblicazione su Instagram. L'utente deve rivedere le clip e i sottotitoli.

## Esecuzione locale alternativa

Il file `AVVIA_STUDIO.bat` non è incluso in questa versione online: il deploy avviene direttamente da Streamlit Community Cloud.
