"""
Pipeline bout-en-bout - Semaines 6&8 (V6/V7/V8)
===============================================
Orchestrateur LOCAL qui ferme la boucle via la facade OpenAI-compatible
(server.py, tunnel SSH localhost:8765/8766 - ou tout autre fournisseur) et
BlueSky local :

  texte ATC --/v1/audio/speech (voix clonee) + VHF client--> audio
        --/v1/audio/transcriptions--> transcription
        --ai_client.interpret (LLM + KB + validation)--> JSON/TrafScript
        --> BlueSky execute --> etat des vols

Demontre : synthese vocale (S6), re-transcription (boucle voix), interpretation
ancree (S5) et execution simulateur (S8). Sauvegarde les audios dans demo_out/.

Prerequis : tunnel ouvert (tunnel.sh) + facade lancee (job_server.slurm) + venv BlueSky.
Lancer :  bluesky-env/Scripts/python.exe pipeline_e2e.py
"""
import os
import json
import argparse
import requests

import bluesky_runtime as bsk

SERVER = os.environ.get("ATC_SERVER", "http://localhost:8765")       # STT + LLM (GPU0)
TTS_SERVER = os.environ.get("ATC_TTS_SERVER", "http://localhost:8766")  # TTS XTTS (GPU1)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_out")

# .env d'abord (si present) : une config utilisateur prime sur les defauts
# facade ci-dessous. Ensuite seulement, setdefault vers la facade tunnel.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass
os.environ.setdefault("ATC_STT_URL", SERVER)
os.environ.setdefault("ATC_LLM_URL", SERVER)
os.environ.setdefault("ATC_TTS_URL", TTS_SERVER)
os.environ.setdefault("ATC_STT_MODEL", "whisper-atc-lora")
os.environ.setdefault("ATC_LLM_MODEL", "mistral-7b-atc")
os.environ.setdefault("ATC_TTS_MODEL", "xtts-atc")

_AI = None


def _ai():
    global _AI
    if _AI is None:
        import ai_client
        _AI = ai_client.AIClient()
    return _AI

# scenario : (instruction du controleur, voix de reference a cloner)
SCENARIO = [
    ("air france one two three four descend flight level one hundred", "pilot_1.wav"),
    ("air france one two three four turn right heading two seven zero", "pilot_1.wav"),
    ("csa one delta zulu climb flight level two four zero reduce speed two five zero", "pilot_3.wav"),
]


def wer(ref, hyp):
    r, h = ref.lower().split(), hyp.lower().split()
    n, m = len(r), len(h)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = 0 if r[i - 1] == h[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
    return d[n][m] / max(1, n)


def _hdr(key_env):
    k = os.environ.get(key_env, "").strip()
    return {"Authorization": f"Bearer {k}"} if k else {}


def tts(text, voice, vhf=True):
    """POST /v1/audio/speech (contrat OpenAI) ; degradation VHF cote client."""
    r = requests.post(f"{os.environ['ATC_TTS_URL'].rstrip('/')}/v1/audio/speech",
                      headers=_hdr("ATC_TTS_KEY"),
                      json={"model": os.environ["ATC_TTS_MODEL"], "input": text,
                            "voice": voice, "response_format": "wav"}, timeout=180)
    r.raise_for_status()
    if not vhf:
        return r.content
    import ai_client
    return ai_client._apply_vhf(r.content)


def asr(wav_bytes):
    """POST /v1/audio/transcriptions (contrat OpenAI)."""
    r = requests.post(f"{os.environ['ATC_STT_URL'].rstrip('/')}/v1/audio/transcriptions",
                      headers=_hdr("ATC_STT_KEY"),
                      files={"file": ("utt.wav", wav_bytes, "audio/wav")},
                      data={"model": os.environ["ATC_STT_MODEL"]}, timeout=180)
    r.raise_for_status()
    return r.json()["text"]


def interpret(text):
    """Interpretation via le client unifie (LLM + KB inlinee + validation bornes)."""
    return _ai().interpret(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--advance", type=float, default=90.0, help="secondes de sim par instruction")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"[*] serveur : {SERVER} | modeles : {requests.get(SERVER + '/v1/models', timeout=30).json()}")
    bsk.bs(); bsk.reset()
    created = {}
    wers = []

    for i, (text, voice) in enumerate(SCENARIO, 1):
        print(f"\n================= ECHANGE {i} =================")
        print(f"[controleur] {text}")

        # 1) synthese vocale (voix clonee + VHF)
        wav = tts(text, voice, vhf=True)
        wpath = os.path.join(OUT, f"ex{i}_{voice.replace('.wav','')}.wav")
        with open(wpath, "wb") as f:
            f.write(wav)
        print(f"  1) TTS  -> {wpath} ({len(wav)} octets, voix={voice}, VHF)")

        # 2) re-transcription (boucle voix)
        stt = asr(wav)
        w = wer(text, stt)
        wers.append(w)
        print(f"  2) STT  -> \"{stt}\"  (WER vs texte = {w*100:.0f} %)")

        # 3) interpretation ancree -> JSON/TrafScript
        res = interpret(stt)
        print(f"  3) interpretation -> {json.dumps(res['orders'], ensure_ascii=False)}")
        if res["rejected"]:
            print(f"     rejets securite : {res['rejected']}")

        # 4) execution BlueSky
        for o in res["orders"]:
            cs = o.get("callsign")
            if cs and cs not in created:
                bsk.create(cs, "A320", 48.0 + 0.1 * len(created), 2.0, 90, 12000, 250)
                created[cs] = True
        before = {s["id"]: s for s in bsk.state()}
        for line in res["trafscript"]:
            bsk.cmd(line)
            print(f"  4) BlueSky <- {line}")
        bsk.advance(args.advance)
        after = {s["id"]: s for s in bsk.state()}
        for line in res["trafscript"]:
            cs = line.split()[1] if len(line.split()) > 1 else None
            if cs in before and cs in after:
                b, a = before[cs], after[cs]
                print(f"     {cs} : hdg {b['hdg']}->{a['hdg']} | alt_ft {b['alt_ft']}->{a['alt_ft']} | cas {b.get('cas_kt')}->{a.get('cas_kt')}")

    print(f"\n[V6/V7/V8] boucle complete OK | WER moyen re-transcription = {100*sum(wers)/len(wers):.0f} %")
    print(f"[*] audios : {OUT}")


if __name__ == "__main__":
    main()
