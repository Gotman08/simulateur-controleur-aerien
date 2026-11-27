"""
Inference NVIDIA-NemotronLabs-VoiceChat-11B sur les stimuli ATC (cote ROMEO)
===========================================================================
Execute le modele bout-en-bout parole-a-parole sur les MEMES enonces
controleur que le banc `bench/e2e_bench.py` (voix SAPI + canal radio VHF,
graine de bruit fixee), de facon a obtenir une comparaison APPARIEE avec la
chaine en cascade Whisper-LoRA -> Mistral-7B -> XTTS deja mesuree sur le
meme cluster (`bench/results/e2e_bench_romeo.json`).

Deux modes, tous deux enregistres :
  * s2s : `run_offline_inference` - le modele repond au micro (collationnement
    pilote) ; on recupere le texte agent + l'audio 22,05 kHz.
  * fc  : `run_fc_offline_inference` - inference en deux passes ; le canal
    d'appel d'outil doit produire l'ordre structure (equivalent du JSON
    d'ordres du LLM de la cascade), ensuite valide par le MEME code de
    production cote local (`atc_llm.postprocess_orders`).

Le script ne fait qu'INFERER et mesurer : aucune metrique n'est calculee ici,
le scoring est realise localement avec le code de production du depot.

Sorties : <output-dir>/results.json + <output-dir>/wav/<id>_agent.wav

Usage (dans le job d'allocation, via srun --overlap) :
  python voicechat_infer.py --checkpoint /dev/shm/vc/ckpt \
      --manifest /dev/shm/vc/stim/manifest.json \
      --output-dir /dev/shm/vc/out/run1 --mode both
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

TARGET_SR = 22050


# --------------------------------------------------------------------------
# Invite systeme ATC - ASCII strict (exigence de la carte modele : pas de
# ponctuation Unicode ni d'emoji dans l'invite systeme ni dans les reponses
# d'API). Les regles de conversion sont celles de `src/atc_llm.SYSTEM`, pour
# que la comparaison porte sur le MODELE et non sur l'ingenierie d'invite.
# --------------------------------------------------------------------------
ATC_SYSTEM_MESSAGE = (
    "You are the pilot of an airliner flying in controlled airspace. "
    "You are listening to the air traffic control (ATC) radio frequency. "
    "Every user turn is a radio transmission from the air traffic controller. "
    "\n\n"
    "Do two things for every clearance you hear:\n"
    "1. Call the tool set_flight_order once for each instruction, with the exact "
    "values spoken by the controller. This is how the aircraft actually executes "
    "the clearance, so it is mandatory.\n"
    "2. Answer on the radio with the standard ICAO read back and nothing else: "
    "repeat the instruction, then say your callsign. Keep it short, no chatter, "
    "no greetings, no questions.\n"
    "\n"
    "Conversion rules for the tool arguments:\n"
    "- spelled out numbers become integers: 'two seven zero' is 270, "
    "'one two three four' is 1234.\n"
    "- 'flight level' N or 'FL' N means action ALT with value = N * 100 feet; "
    "an altitude given in feet is used as is.\n"
    "- heading is in degrees, action HDG; speed is in knots, action SPD; "
    "'direct to' a waypoint is action ADDWPT with the waypoint name.\n"
    "- callsigns use the ICAO airline code plus the flight number: "
    "air france is AFR, speedbird is BAW, lufthansa is DLH, ryanair is RYR, "
    "easyjet is EZY, klm is KLM, american is AAL, united is UAL, csa is CSA. "
    "A spelled registration uses the phonetic alphabet, so 'csa one delta zulu' "
    "is CSA1DZ.\n"
    "- use only the four actions HDG, ALT, SPD and ADDWPT. Ignore purely "
    "informational items such as QNH, altimeter settings or frequency changes.\n"
    "\n"
    "Read back numbers digit by digit, as pilots do on the radio."
)

ATC_TOOLS = [
    {
        "function": {
            "name": "set_flight_order",
            "description": (
                "Apply an air traffic control clearance to the aircraft. "
                "Call it once for every instruction heard on the radio."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "callsign": {
                        "type": "string",
                        "description": "ICAO callsign of the aircraft, for example AFR1234, BAW57 or CSA1DZ",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["HDG", "ALT", "SPD", "ADDWPT"],
                        "description": (
                            "HDG for a heading in degrees, ALT for an altitude in feet, "
                            "SPD for a speed in knots, ADDWPT to proceed direct to a waypoint"
                        ),
                    },
                    "value": {
                        "type": "integer",
                        "description": (
                            "Numeric value: degrees for HDG, feet for ALT "
                            "(flight level multiplied by 100), knots for SPD, 0 for ADDWPT"
                        ),
                    },
                    "waypoint": {
                        "type": "string",
                        "description": "Waypoint name, only for the ADDWPT action",
                    },
                },
                "required": ["callsign", "action", "value"],
            },
        }
    }
]

# Variante SANS declaration d'outils : mesure la comprehension par le seul
# collationnement parle (condition temoin de l'ingenierie d'invite).
ATC_SYSTEM_SIMPLE = (
    "You are an airline pilot talking on the air traffic control radio. "
    "The user is the air traffic controller. As soon as the controller finishes "
    "speaking, answer out loud. Always answer by reading back the instruction you "
    "heard, then your callsign, exactly as pilots do: for example, if you hear "
    "'air france one two three four turn left heading two seven zero', you say "
    "'turn left heading two seven zero, air france one two three four'. "
    "Keep answering every transmission."
)

# Reponse d'outil injectee en passe 2 (le simulateur accuse reception).
ATC_API_RESPONSE = {
    "tool_name": "set_flight_order",
    "response": {"status": "executed"},
}


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------
# Entrees/sorties audio SANS torchaudio.load/save : sur ce cluster aarch64,
# torchaudio 2.10 delegue a `torchcodec` (aucune roue 0.10 aarch64, et il
# faudrait aussi FFmpeg dans l'environnement). On lit/ecrit donc en direct
# avec soundfile + scipy - operation strictement equivalente (mono, 16 kHz)
# a `offline_voicechat.load_wav_16k_mono`, dont c'est la seule fonction.
# --------------------------------------------------------------------------
def load_wav_16k_mono_sf(path, device="cuda"):
    import numpy as np
    import soundfile as sf
    import torch
    from math import gcd
    from scipy.signal import resample_poly

    data, sr = sf.read(path, dtype="float32", always_2d=False)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        g = gcd(int(sr), 16000)
        data = resample_poly(data, 16000 // g, int(sr) // g)
    data = np.ascontiguousarray(data, dtype=np.float32)
    wav = torch.from_numpy(data)
    input_signal = wav.unsqueeze(0).to(device)
    input_signal_lens = torch.tensor([wav.shape[0]], device=device)
    return wav, input_signal, input_signal_lens


def save_wav_sf(path, tensor_2d, sr):
    import soundfile as sf
    arr = tensor_2d.squeeze(0).float().cpu().numpy()
    sf.write(path, arr, sr, subtype="PCM_16")


# --------------------------------------------------------------------------
# Extraction des appels d'outil depuis le canal dedie, en UNE passe.
# `run_fc_offline_inference` du depot NeMo fait deux passes parce qu'il veut
# reinjecter la reponse d'API et continuer a parler ; pour MESURER l'ordre
# compris, la passe 1 suffit. Meme logique d'analyse que la reference
# (nettoyage des <SPECIAL_20/21>, balises <TOOLCALL>, JSON objet ou tableau).
# --------------------------------------------------------------------------
def extraire_appels(model, res):
    fc = res.get("tokens_function_pred", res.get("tokens_function"))
    if fc is None:
        return [], []
    try:
        positions = model.stt_model._extract_function_call_positions(
            fc, res.get("tokens_len"), res.get("tokens_text"))
    except Exception as e:
        return [], [f"extraction impossible: {type(e).__name__}: {e}"]
    appels, bruts = [], []
    for info in positions:
        for call in info.get("function_calls", []):
            texte = call.get("call_text", "")
            bruts.append(texte)
            clean = texte.replace("<SPECIAL_20>", "").replace("<SPECIAL_21>", "").strip()
            if "<TOOLCALL>" in clean:
                clean = clean.split("<TOOLCALL>")[1].split("</TOOLCALL>")[0].strip()
            try:
                data = json.loads(clean) if clean.startswith("[") else [json.loads(clean)]
            except Exception:
                continue
            for tc in data:
                if not isinstance(tc, dict):
                    continue
                args = tc.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                appels.append({"name": tc.get("name", ""), "arguments": args,
                               "step": call.get("start_pos"), "raw": texte})
    return appels, bruts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--manifest", required=True,
                    help="JSON: [{id, wav, condition}, ...]")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--mode", choices=["fc1", "s2s", "fc", "both"], default="fc1",
                    help="fc1 = une passe (texte + appels d'outil) ; s2s/fc/both "
                         "ajoutent le decodage audio, environ 10x plus couteux")
    ap.add_argument("--invite", choices=["outils", "simple"], default="outils",
                    help="invite systeme : avec declaration d'outils, ou consigne "
                         "de collationnement seule")
    ap.add_argument("--template", default="/dev/shm/vc/Speech/examples/speechlm2/"
                                          "function_calling/template.jinja")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=0, help="0 = tous les stimuli")
    ap.add_argument("--save-audio", action="store_true", default=True)
    ap.add_argument("--warmup-wav", default="")
    args = ap.parse_args()

    import torch
    from nemo.collections.speechlm2.inference.utils.offline_voicechat import (
        build_model,
        encode_system_prompt,
        render_fc_system_prompt,
        run_fc_offline_inference,
        run_offline_inference,
        splice_fc_audio_gap,
    )
    load_wav_16k_mono = load_wav_16k_mono_sf

    os.makedirs(os.path.join(args.output_dir, "wav"), exist_ok=True)
    with open(args.manifest, encoding="utf-8") as f:
        items = json.load(f)
    if args.limit:
        items = items[: args.limit]

    log(f"[vc] {len(items)} stimuli ; mode={args.mode} ; checkpoint={args.checkpoint}")

    t0 = time.perf_counter()
    model = build_model(args.checkpoint, device=args.device)
    t_build = time.perf_counter() - t0
    log(f"[vc] modele charge en {t_build:.1f} s")

    # invite systeme avec outils (gabarit officiel du depot NeMo)
    system_prompt = (render_fc_system_prompt(args.template, ATC_SYSTEM_MESSAGE, ATC_TOOLS)
                     if args.invite == "outils" else ATC_SYSTEM_SIMPLE)
    log(f"[vc] invite systeme : {len(system_prompt)} caracteres ; "
        f"ASCII strict = {system_prompt.isascii()}")
    prompt_tokens, prompt_token_lens = encode_system_prompt(
        model, system_prompt, device=args.device)

    # ------- rodage (exclu des mesures) -----------------------------------
    warm = args.warmup_wav or items[0]["wav"]
    try:
        w1, isig, ilen = load_wav_16k_mono(warm, device=args.device)
        tw = time.perf_counter()
        _ = run_offline_inference(model, input_signal=isig, input_signal_lens=ilen,
                                  prompt_tokens=prompt_tokens,
                                  prompt_token_lens=prompt_token_lens,
                                  decode_audio=True)
        log(f"[vc] rodage effectue en {time.perf_counter() - tw:.1f} s")
    except Exception:
        log("[vc] rodage en echec :\n" + traceback.format_exc())

    rows = []
    for i, it in enumerate(items):
        row = {"id": it["id"], "condition": it.get("condition", ""),
               "wav": it["wav"], "phrase": it.get("phrase", "")}
        try:
            wav_1d, isig, ilen = load_wav_16k_mono(it["wav"], device=args.device)
            row["duree_entree_s"] = wav_1d.shape[0] / 16000.0

            # ---------- mode fc1 : UNE passe, sans decodage audio ---------
            if args.mode == "fc1":
                torch.cuda.synchronize()
                t = time.perf_counter()
                res = run_offline_inference(
                    model, input_signal=isig, input_signal_lens=ilen,
                    prompt_tokens=prompt_tokens, prompt_token_lens=prompt_token_lens,
                    decode_audio=False)
                torch.cuda.synchronize()
                row["s2s_latence_s"] = time.perf_counter() - t
                row["s2s_texte"] = res.get("text", [""])[0]
                appels, bruts = extraire_appels(model, res)
                row["fc_appels"] = appels
                row["fc_bruts"] = bruts
                if i == 0:
                    row["_cles_resultat"] = sorted(
                        k for k in res.keys() if not k.startswith("_"))

            # ---------- mode s2s : une seule passe, audio decode ----------
            if args.mode in ("s2s", "both"):
                torch.cuda.synchronize()
                t = time.perf_counter()
                res = run_offline_inference(
                    model, input_signal=isig, input_signal_lens=ilen,
                    prompt_tokens=prompt_tokens, prompt_token_lens=prompt_token_lens,
                    decode_audio=True)
                torch.cuda.synchronize()
                row["s2s_latence_s"] = time.perf_counter() - t
                row["s2s_texte"] = res.get("text", [""])[0]
                if i == 0:
                    row["_cles_resultat"] = sorted(
                        k for k in res.keys() if not k.startswith("_"))
                if res.get("audio") is not None and args.save_audio:
                    n = res["audio_len"][0].item()
                    a = res["audio"][0, :n].cpu().unsqueeze(0)
                    p = os.path.join(args.output_dir, "wav", f"{it['id']}_s2s.wav")
                    save_wav_sf(p, a, TARGET_SR)
                    row["s2s_audio"] = p
                    row["s2s_audio_duree_s"] = a.shape[1] / TARGET_SR
                    row["s2s_rtf"] = row["s2s_latence_s"] / max(1e-6, row["s2s_audio_duree_s"])

            # ---------- mode fc : deux passes, appel d'outil --------------
            if args.mode in ("fc", "both"):
                torch.cuda.synchronize()
                t = time.perf_counter()
                res2, fc_out, call_step, resp_step, resp_ids = run_fc_offline_inference(
                    model, input_signal=isig, input_signal_lens=ilen,
                    prompt_tokens=prompt_tokens, prompt_token_lens=prompt_token_lens,
                    api_response=ATC_API_RESPONSE, device=args.device)
                torch.cuda.synchronize()
                row["fc_latence_s"] = time.perf_counter() - t
                row["fc_texte"] = res2.get("text", [""])[0]
                row["fc_appels"] = fc_out.get("tool_calls", [])
                row["fc_call_step"] = call_step
                if res2.get("audio") is not None and args.save_audio:
                    n = res2["audio_len"][0].item()
                    a = res2["audio"][0, :n].cpu().unsqueeze(0)
                    a = splice_fc_audio_gap(a, call_step, resp_step, len(resp_ids))
                    p = os.path.join(args.output_dir, "wav", f"{it['id']}_fc.wav")
                    save_wav_sf(p, a, TARGET_SR)
                    row["fc_audio"] = p
                    row["fc_audio_duree_s"] = a.shape[1] / TARGET_SR

            log(f"  [{i + 1:3d}/{len(items)}] {it['id']:<18} "
                f"s2s={row.get('s2s_latence_s', float('nan')):.2f}s "
                f"fc={row.get('fc_latence_s', float('nan')):.2f}s "
                f"outils={len(row.get('fc_appels', []))} "
                f"| {str(row.get('s2s_texte', ''))[:70]!r}")
        except Exception:
            row["erreur"] = traceback.format_exc()
            log(f"  [{i + 1:3d}/{len(items)}] {it['id']} ECHEC\n{row['erreur']}")
        rows.append(row)

        # ecriture incrementale (le job peut etre interrompu)
        with open(os.path.join(args.output_dir, "results.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"modele": "nvidia/NVIDIA-NemotronLabs-VoiceChat-11B",
                       "checkpoint": args.checkpoint,
                       "mode": args.mode,
                       "invite_systeme": system_prompt,
                       "message_systeme_atc": ATC_SYSTEM_MESSAGE,
                       "outils": ATC_TOOLS,
                       "chargement_modele_s": t_build,
                       "gpu": __import__("torch").cuda.get_device_name(0),
                       "torch": __import__("torch").__version__,
                       "rows": rows}, f, indent=1, ensure_ascii=False)

    log(f"[vc] termine -> {os.path.join(args.output_dir, 'results.json')}")


if __name__ == "__main__":
    sys.exit(main())
