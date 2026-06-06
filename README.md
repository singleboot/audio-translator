# Audio Translator v1

A local web app that watches a folder for new audio files, transcribes the
source, translates to many target languages, and synthesises speech in the
**original voice** for every (engine, language) combination you enable.

- **ASR:** Whisper (local, free)
- **Translators (pick one):** NLLB-200 (local, free) · Gemini (free tier) ·
  OpenAI · Custom HTTP · Noop (passthrough)
- **TTS engines (8):** Indic-Parler-TTS · Qwen3-TTS · k2-fsa OmniVoice ·
  Coqui XTTSv2 · Edge TTS (free) · OpenAI · ElevenLabs · Sarvam.ai
- **UI:** single HTML page, no build step, live updates over WebSocket
- **Output:** flat `outputs/<source_stem>_<engine>_<lang>.wav`

## Quick start (one-click installer)

```powershell
# Windows
setup.bat
run.bat
```

```bash
# Linux / macOS
bash setup.sh
bash run.sh
```

## Quick start (manual)

```powershell
# 1. Create a venv
python -m venv .venv
.\.venv\Scripts\activate

# 2. Install PyTorch first (CUDA 12.1 wheels shown; pick the version that
#    matches your GPU + CUDA toolkit; CPU-only works but is slow)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 3. Install app dependencies
pip install -r requirements.txt

# 4. (Optional) Install the TTS engines you want to use
pip install git+https://github.com/huggingface/parler-tts.git  # Indic-Parler-TTS
pip install TTS              # Coqui XTTSv2
pip install qwen-tts         # Qwen3-TTS
pip install edge-tts         # Edge TTS CLI
pip install elevenlabs       # ElevenLabs
# pip install omnivoice     # k2-fsa OmniVoice

# 5. Edit config.yaml — set API keys for any cloud providers.

# 6. Run
python run.py
# open http://127.0.0.1:8000
```

## Usage

1. In the UI, toggle the TTS engines and pick the target languages.
2. Click **Save settings**.
3. Click **Start watcher** (or use the manual upload).
4. Drop an audio file into the configured `watch` folder.
5. The job shows up in the **Recent jobs** table; finished clips land in
   the **Playback queue** and auto-play sequentially.

Output files are written to `outputs/<stem>_<engine>_<lang>.wav`.

## TTS engines

| Engine | Type | Languages | Voice Clone | Network |
|---|---|---|---|---|
| **Indic-Parler-TTS** | local (0.9B) | 21 Indic + English | Named speakers (69) | No* |
| **Qwen3-TTS** | local (1.7B) | 10 major langs | Yes | No* |
| **k2-fsa OmniVoice** | local | 600+ langs | Yes | No* |
| **Coqui XTTSv2** | local | 17 langs | Yes | No* |
| **Edge TTS** | cloud (free) | 32 langs | No | Yes |
| **OpenAI TTS** | cloud (paid) | many | No | Yes |
| **ElevenLabs** | cloud (paid) | many | Yes | Yes |
| **Sarvam.ai** | cloud (paid) | Indian langs + EN | Yes | Yes |

\* Model weights downloaded on first use (≈ 2 GB for Indic-Parler-TTS).

## Languages supported by Indic-Parler-TTS

Assamese · Bengali · Bodo · Dogri · English · Gujarati · Hindi · Kannada ·
Konkani · Maithili · Malayalam · Manipuri · Marathi · Nepali · Odia ·
Sanskrit · Santali · Sindhi · Tamil · Telugu · Urdu

69 named speakers (Rohit, Divya, Sita, Arjun, Thoma, etc.) provide
voice consistency without reference audio.

## What runs where

| Stage | Default | Alternative |
|---|---|---|
| ASR | Whisper `large-v3-turbo` (local GPU) | — |
| Translate | Noop (passthrough) | NLLB-200 · Gemini · OpenAI · Custom HTTP |
| TTS (clone) | whatever engines you enable | Indic-Parler-TTS, Qwen3-TTS, XTTS, OmniVoice, ElevenLabs |
| TTS (no clone) | Edge TTS (free) | OpenAI TTS, Sarvam.ai |

GPU stages (Whisper · NLLB · XTTS · Qwen3-TTS · OmniVoice · Indic-Parler-TTS)
share one GPU. The pipeline runs them sequentially to avoid OOM, then fans
out TTS engines in parallel up to `pipeline.max_parallel_tts`.

## Configuration

Everything lives in `config.yaml`. See comments inside for each key.

The most common things to change:
- `paths.watch_folder` / `paths.output_folder`
- `tts.enabled` (which engines to use by default)
- `languages` (which target languages to generate)
- API keys for the cloud providers you want to enable

## Folder layout

```
Audio_trans_v1/
├── app/
│   ├── asr/             # Whisper
│   ├── translators/     # NLLB, Gemini, OpenAI, Custom HTTP, Noop
│   ├── tts/             # 8 engines: indic_parler_tts, qwen3_tts, k2_omnivoice,
│   │                    #   coqui_xtts, edge_tts, openai_tts, elevenlabs_tts, sarvam_tts
│   ├── static/          # UI (index.html, app.js, style.css)
│   ├── config.py        # YAML loader / merger
│   ├── db.py            # SQLite for jobs + artifacts
│   ├── main.py          # FastAPI app + REST + WebSocket
│   ├── pipeline.py      # ASR -> translate -> TTS orchestrator
│   ├── watcher.py       # Watchdog observer with debounce
│   └── ws.py            # WebSocket pub/sub
├── outputs/             # generated .wav files (flat)
├── watch/               # drop files here
├── config.yaml
├── requirements.txt
├── run.py
├── setup.bat            # Windows one-click installer
├── setup.sh             # Linux/macOS one-click installer
├── run.bat              # Windows launcher
├── run.sh               # Linux/macOS launcher
└── README.md
```

## One-click setup from GitHub

Clone anywhere, then run:

```powershell
git clone https://github.com/<your>/<repo>.git
cd <repo>
setup.bat     # or bash setup.sh
run.bat       # or bash run.sh
```

Everything is self-contained in one folder. Move it, rename it, clone it
again — it always works.

## License

MIT for the integration code. Individual engines retain their own licenses
(Indic-Parler-TTS = Apache 2.0, Coqui XTTS = CPML, Qwen3-TTS = Apache 2.0,
Edge TTS = Microsoft ToS, etc.). Voice cloning must comply with the laws
of your jurisdiction and the consent of any speaker you clone.
