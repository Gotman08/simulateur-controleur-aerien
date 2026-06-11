# =====================================================================
#  Lancement du backend IA ROMEO en UNE commande (Windows / PowerShell)
#  ---------------------------------------------------------------------
#  1. soumet job_server.slurm sur le cluster (Whisper + Mistral + XTTS),
#  2. attend que le job demarre et recupere le noeud de calcul,
#  3. ouvre le tunnel SSH localhost:8765/8766 -> noeud (reste ouvert),
#  -> l'application (atc_app.py) detecte alors ROMEO automatiquement
#     (badge ROMEO en haut a droite, ou clic sur le badge pour re-detecter).
#
#  Usage :   .\start_romeo.ps1            (depuis la racine du projet)
#  Arret :   Ctrl+C (ferme le tunnel) puis .\start_romeo.ps1 -Cancel
#  Prerequis : acces "ssh romeo" configure (cle + alias dans ~/.ssh/config).
# =====================================================================
param(
    [switch]$Cancel,          # annule le(s) job(s) wh-server en cours
    [string]$Work = "/gpfs/scratch/nimarano/atc-whisper-s4"
)

$ErrorActionPreference = "Stop"

if ($Cancel) {
    ssh romeo "scancel --name=wh-server"
    Write-Host "[romeo] jobs wh-server annules."
    exit 0
}

# --- 1. job deja en cours ? sinon soumission --------------------------------
$existing = (ssh romeo "squeue -u `$(whoami) --name=wh-server -h -o '%i %T %N'") -split "`n" |
            Where-Object { $_ -match "RUNNING" } | Select-Object -First 1
if ($existing) {
    $node = ($existing -split "\s+")[2]
    Write-Host "[romeo] serveur deja actif sur $node"
} else {
    $sub = ssh romeo "cd $Work && sbatch job_server.slurm"
    if ($sub -notmatch "Submitted batch job (\d+)") { throw "soumission SLURM echouee : $sub" }
    $jobid = $Matches[1]
    Write-Host "[romeo] job $jobid soumis, attente du demarrage (file d'attente)..."

    # --- 2. attente du noeud (max 20 min) ------------------------------------
    $node = $null
    foreach ($i in 1..120) {
        Start-Sleep -Seconds 10
        $line = ssh romeo "squeue -j $jobid -h -o '%T %N'"
        if ($line -match "^RUNNING\s+(\S+)") { $node = $Matches[1]; break }
        Write-Host "  ... etat: $($line.Trim()) ($([int]($i*10/6))/120 min)"
    }
    if (-not $node) { throw "le job $jobid n'a pas demarre (squeue) — reessayez plus tard." }
    Write-Host "[romeo] job $jobid actif sur $node — chargement des modeles (~5-10 min au premier appel)"
}

# --- 3. tunnel SSH (bloquant : laisser cette fenetre ouverte) ----------------
Write-Host "[romeo] tunnel localhost:8765 (ASR+LLM) / localhost:8766 (TTS) -> $node"
Write-Host "[romeo] laissez cette fenetre OUVERTE ; lancez l'application dans une autre fenetre."
ssh -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -N `
    -L "8765:${node}:8765" -L "8766:${node}:8766" romeo
