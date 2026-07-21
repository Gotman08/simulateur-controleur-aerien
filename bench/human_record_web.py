"""
Enregistrement des 25 clairances par un locuteur humain - via NAVIGATEUR
========================================================================
Alternative a human_record.py pour les machines ou la capture PortAudio est
bloquee (protection micro antivirus, pile d'effets constructeur...). Le
navigateur utilise exactement la meme voie de capture que le push-to-talk
de l'application (getUserMedia + ScriptProcessor), qui fonctionne deja sur
ce poste.

Lance un petit serveur local, ouvre la page dans le navigateur : la page
affiche chaque phrase, enregistre le micro, permet de reecouter et refaire,
puis envoie la prise au serveur qui la sauvegarde en WAV 16 kHz mono
(bench/results/human_audio/<locuteur>/cNN_clean.wav - meme format que
human_record.py ; bench/human_e2e.py s'utilise ensuite a l'identique).

Execution :
  bench\\bench-env\\Scripts\\python.exe bench\\human_record_web.py --speaker nicolas
Puis dans la page : autoriser le micro, lire les phrases. Ctrl+C pour finir.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

OUT_SR = 16000

PAGE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Enregistrement des clairances - locuteur humain</title>
<style>
 body{font-family:system-ui,Segoe UI,sans-serif;max-width:860px;margin:2rem auto;
      padding:0 1rem;background:#0d1526;color:#e8edf6}
 h1{font-size:1.25rem;color:#7fb2ff}
 #phrase{font-size:1.5rem;background:#16233f;border:1px solid #2c4271;
         border-radius:8px;padding:1.2rem;margin:1rem 0;line-height:1.5}
 button{font-size:1.05rem;padding:.55rem 1.2rem;margin:.25rem;border-radius:8px;
        border:1px solid #2c4271;background:#1d2f52;color:#e8edf6;cursor:pointer}
 button:disabled{opacity:.35;cursor:default}
 #rec.on{background:#7a1f1f;border-color:#c33}
 #meter{height:10px;background:#16233f;border-radius:5px;margin:.6rem 0;overflow:hidden}
 #meterfill{height:100%;width:0;background:#3fa060}
 #status{min-height:1.4em;color:#9fb4d8}
 #list{margin-top:1.2rem;font-size:.9rem;columns:2}
 .done{color:#3fa060}.todo{color:#68789a}.cur{color:#7fb2ff;font-weight:600}
 .warn{color:#e0a03f}
</style></head><body>
<h1>Boucle vocale avec locuteur humain - enregistrement (__SPEAKER__)</h1>
<p>Pièce calme, débit naturel de phraséologie. Si tu te trompes en lisant,
refais la prise : la vérité terrain est la phrase écrite.</p>
<div id="phrase">…</div>
<div id="meter"><div id="meterfill"></div></div>
<div>
 <button id="init">1. Activer le micro</button>
 <button id="rec" disabled>2. Enregistrer</button>
 <button id="play" disabled>Réécouter</button>
 <button id="redo" disabled>Refaire</button>
 <button id="keep" disabled>3. Garder &rarr; suivante</button>
</div>
<div id="status"></div>
<div id="list"></div>
<script>
let phrases=[], done=[], cur=0, ctx, proc, chunks=[], recording=false,
    take=null, takeSr=0, player=null;
const $=id=>document.getElementById(id);
function pick(){ cur=done.findIndex(d=>!d); if(cur<0) cur=phrases.length-1; show(); }
function show(){
  $('phrase').textContent='Phrase '+(cur+1)+'/'+phrases.length+' :  « '+phrases[cur]+' »';
  $('list').innerHTML=phrases.map((p,i)=>{
    const cls=i===cur?'cur':(done[i]?'done':'todo');
    return '<div class="'+cls+'">'+(done[i]?'&#10003; ':'&#9633; ')+(i+1)+'. '+p+'</div>';
  }).join('');
  if(done.every(d=>d)) $('status').textContent=
    'Terminé ! Les 25 prises sont sauvegardées. Ferme cette page, arrête le '+
    'serveur (Ctrl+C) et lance bench\\\\human_e2e.py';
}
async function init(){
  const stream=await navigator.mediaDevices.getUserMedia({audio:true});
  ctx=new (window.AudioContext||window.webkitAudioContext)();
  const srcN=ctx.createMediaStreamSource(stream);
  proc=ctx.createScriptProcessor(4096,1,1);
  const mute=ctx.createGain(); mute.gain.value=0;
  srcN.connect(proc); proc.connect(mute); mute.connect(ctx.destination);
  proc.onaudioprocess=e=>{
    const d=e.inputBuffer.getChannelData(0);
    let peak=0; for(let i=0;i<d.length;i++) peak=Math.max(peak,Math.abs(d[i]));
    $('meterfill').style.width=Math.min(100,peak*130)+'%';
    if(recording) chunks.push(new Float32Array(d));
  };
  $('init').disabled=true; $('rec').disabled=false;
  $('status').textContent='Micro actif ('+ctx.sampleRate+' Hz). Enregistre la phrase affichée.';
}
function concat(){
  const n=chunks.reduce((s,c)=>s+c.length,0), out=new Float32Array(n);
  let o=0; for(const c of chunks){out.set(c,o); o+=c.length;} return out;
}
function wavBlob(f32,sr){
  const b=new ArrayBuffer(44+f32.length*2), v=new DataView(b);
  const ws=(o,s)=>{for(let i=0;i<s.length;i++)v.setUint8(o+i,s.charCodeAt(i));};
  ws(0,'RIFF'); v.setUint32(4,36+f32.length*2,true); ws(8,'WAVEfmt ');
  v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true);
  v.setUint32(24,sr,true); v.setUint32(28,sr*2,true); v.setUint16(32,2,true);
  v.setUint16(34,16,true); ws(36,'data'); v.setUint32(40,f32.length*2,true);
  for(let i=0;i<f32.length;i++){const s=Math.max(-1,Math.min(1,f32[i]));
    v.setInt16(44+i*2, s<0?s*0x8000:s*0x7FFF, true);}
  return new Blob([b],{type:'audio/wav'});
}
function toggleRec(){
  if(!recording){ chunks=[]; recording=true; $('rec').textContent='ARRÊTER';
    $('rec').classList.add('on');
    $('play').disabled=$('redo').disabled=$('keep').disabled=true;
    $('status').textContent='Enregistrement… parle, puis clique ARRÊTER.'; }
  else{ recording=false; $('rec').textContent='2. Enregistrer';
    $('rec').classList.remove('on');
    take=concat(); takeSr=ctx.sampleRate;
    const dur=take.length/takeSr;
    let peak=0; for(let i=0;i<take.length;i++) peak=Math.max(peak,Math.abs(take[i]));
    if(dur<1.0){ $('status').innerHTML='<span class="warn">Prise trop courte ('
      +dur.toFixed(1)+' s) : recommence.</span>'; take=null; return; }
    if(peak<0.02){ $('status').innerHTML='<span class="warn">Niveau très faible '+
      '(pic '+peak.toFixed(3)+') : micro muet ? Recommence.</span>'; take=null; return; }
    $('status').textContent='Prise : '+dur.toFixed(1)+' s, pic '+peak.toFixed(2)+
      (peak>0.99?'  (attention : saturation probable)':'')+
      '. Réécoute puis garde, ou refais.';
    $('play').disabled=$('redo').disabled=$('keep').disabled=false; }
}
function play(){ if(!take) return;
  if(player) player.pause();
  player=new Audio(URL.createObjectURL(wavBlob(take,takeSr))); player.play(); }
function redo(){ take=null;
  $('play').disabled=$('redo').disabled=$('keep').disabled=true;
  $('status').textContent='Prise abandonnée, enregistre à nouveau.'; }
async function keep(){ if(!take) return;
  $('keep').disabled=true;
  const r=await fetch('/save/'+cur,{method:'POST',
    headers:{'X-Sample-Rate':String(takeSr)}, body:take.buffer});
  if(!r.ok){ $('status').textContent='Erreur serveur : '+r.status; return; }
  done[cur]=true; take=null;
  $('play').disabled=$('redo').disabled=true;
  pick();
  if(!done.every(d=>d)) $('status').textContent='Sauvegardé. Phrase suivante.';
}
$('init').onclick=init; $('rec').onclick=toggleRec; $('play').onclick=play;
$('redo').onclick=redo; $('keep').onclick=keep;
fetch('/state').then(r=>r.json()).then(s=>{phrases=s.phrases; done=s.done; pick();});
</script></body></html>"""


def make_handler(cases, out_dir, speaker):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(200, PAGE.replace("__SPEAKER__", speaker).encode("utf-8"))
            elif self.path == "/state":
                done = [os.path.exists(os.path.join(out_dir, f"c{i:02d}_clean.wav"))
                        for i in range(len(cases))]
                body = json.dumps({"phrases": [c["phrase"] for c in cases],
                                   "done": done}).encode("utf-8")
                self._send(200, body, "application/json")
            else:
                self._send(404, b"?")

        def do_POST(self):
            if not self.path.startswith("/save/"):
                self._send(404, b"?")
                return
            i = int(self.path.rsplit("/", 1)[1])
            n = int(self.headers.get("Content-Length", 0))
            sr = int(self.headers.get("X-Sample-Rate", "48000"))
            raw = self.rfile.read(n)
            data = np.frombuffer(raw, dtype="<f4")
            if sr != OUT_SR:
                from math import gcd
                from scipy.signal import resample_poly
                g = gcd(sr, OUT_SR)
                data = resample_poly(data, OUT_SR // g, sr // g)
            data = np.clip(data, -1.0, 1.0).astype(np.float32)
            import soundfile as sf
            path = os.path.join(out_dir, f"c{i:02d}_clean.wav")
            sf.write(path, data, OUT_SR, subtype="PCM_16")
            print(f"  [{i + 1:2d}/{len(cases)}] sauvegarde -> "
                  f"{os.path.basename(path)}  ({len(data) / OUT_SR:.1f} s)", flush=True)
            self._send(200, b"ok", "text/plain")

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="locuteur1")
    ap.add_argument("--port", type=int, default=8907)
    ap.add_argument("--max-n", type=int, default=25)
    args = ap.parse_args()

    import e2e_bench
    cases = e2e_bench.controller_cases(args.max_n)
    out_dir = os.path.join(HERE, "results", "human_audio", args.speaker)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": f"c{i:02d}", "text": c["phrase"]}
                   for i, c in enumerate(cases)], f, ensure_ascii=False, indent=1)

    url = f"http://127.0.0.1:{args.port}/"
    srv = ThreadingHTTPServer(("127.0.0.1", args.port),
                              make_handler(cases, out_dir, args.speaker))
    print(f"=== Enregistreur web : {url}  (locuteur '{args.speaker}', "
          f"{len(cases)} phrases) ===")
    print("Autorise le micro dans le navigateur, lis les phrases.")
    print("Quand tout est coche : Ctrl+C ici, puis lance bench\\human_e2e.py")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[stop] enregistrements dans", out_dir)


if __name__ == "__main__":
    main()
