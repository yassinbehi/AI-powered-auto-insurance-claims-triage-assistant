<#
    outils/lancer.ps1 — demarre l'application TSA en entier.

    Enchaine : verifications, API, attente de sa disponibilite, interface,
    ouverture du navigateur. A la fermeture, ARRETE LES DEUX PROCESSUS et
    leurs enfants.

    Ce dernier point est la raison d'etre du script. `npm run dev` engendre un
    processus node separe : tuer npm seul laisse un serveur orphelin qui
    occupe le port 3000, et le lancement suivant echoue sans raison visible.
    D'ou le taskkill /T (arbre complet) en sortie, et le controle de ports en
    entree qui rattrape le cas ou un orphelin aurait survecu quand meme.
#>

$ErrorActionPreference = 'Stop'

$racine = Split-Path -Parent $PSScriptRoot
$python = Join-Path $racine '.venv\Scripts\python.exe'
$frontend = Join-Path $racine 'frontend'

$PORT_API = 8000
$PORT_UI  = 3000

function Ecrire($texte, $couleur = 'Gray') { Write-Host $texte -ForegroundColor $couleur }

function Arreter-Arbre($processus) {
    if ($null -eq $processus) { return }
    if ($processus.HasExited) { return }
    # /T : les enfants aussi. C'est tout l'interet.
    taskkill /PID $processus.Id /T /F 2>&1 | Out-Null
}

function Pid-Sur-Le-Port($port) {
    try {
        $lien = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        return ($lien | Select-Object -First 1).OwningProcess
    } catch {
        return $null
    }
}

function Liberer-Le-Port($port, $quoi) {
    $pidOccupant = Pid-Sur-Le-Port $port
    if ($null -eq $pidOccupant) { return $true }

    $nom = 'inconnu'
    try { $nom = (Get-Process -Id $pidOccupant -ErrorAction Stop).ProcessName } catch { }

    Ecrire ""
    Ecrire "Le port $port ($quoi) est deja occupe par $nom (PID $pidOccupant)." 'Yellow'
    Ecrire "C'est souvent un lancement precedent qui n'a pas ete arrete." 'Yellow'
    $reponse = Read-Host "Arreter ce processus et continuer ? [O/n]"
    if ($reponse -eq 'n' -or $reponse -eq 'N') {
        Ecrire "Abandon." 'Red'
        return $false
    }
    taskkill /PID $pidOccupant /T /F 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    if ($null -ne (Pid-Sur-Le-Port $port)) {
        Ecrire "Le port $port est toujours occupe. Abandon." 'Red'
        return $false
    }
    Ecrire "Port $port libere." 'Green'
    return $true
}

function Attendre-Url($url, $secondes, $quoi) {
    $limite = (Get-Date).AddSeconds($secondes)
    while ((Get-Date) -lt $limite) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null
            return $true
        } catch {
            Start-Sleep -Milliseconds 700
        }
    }
    Ecrire "$quoi n'a pas repondu en $secondes secondes." 'Red'
    return $false
}

# ---------------------------------------------------------------------------
# Verifications : echouer ICI avec une phrase utile, plutot que plus loin avec
# une trace Python illisible.
# ---------------------------------------------------------------------------
Ecrire "TSA — Triage Sinistres Auto" 'Cyan'
Ecrire ""

if (-not (Test-Path $python)) {
    Ecrire "Environnement Python introuvable : $python" 'Red'
    Ecrire "Creez-le depuis la racine du projet :" 'Gray'
    Ecrire "    python -m venv .venv" 'Gray'
    Ecrire "    .venv\Scripts\pip install -r backend\requirements.txt" 'Gray'
    Read-Host "Entree pour fermer"
    exit 1
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Ecrire "Dependances de l'interface absentes." 'Red'
    Ecrire "    cd frontend" 'Gray'
    Ecrire "    npm install" 'Gray'
    Read-Host "Entree pour fermer"
    exit 1
}
if (-not (Test-Path (Join-Path $racine 'backend\.env'))) {
    Ecrire "backend\.env absent : la cle API n'est pas configuree." 'Red'
    Ecrire "Creez ce fichier avec la ligne :" 'Gray'
    Ecrire "    ANTHROPIC_API_KEY=sk-ant-..." 'Gray'
    Read-Host "Entree pour fermer"
    exit 1
}

if (-not (Liberer-Le-Port $PORT_API "API")) { Read-Host "Entree pour fermer"; exit 1 }
if (-not (Liberer-Le-Port $PORT_UI  "interface")) { Read-Host "Entree pour fermer"; exit 1 }

$api = $null
$ui = $null

try {
    Ecrire "Demarrage de l'API..." 'Gray'
    # Pas de --reload : le rechargement a chaud redemarre le processus a chaque
    # fichier Python sauvegarde (voir l'en-tete de backend/src/api.py).
    $api = Start-Process -FilePath $python `
        -ArgumentList '-m', 'uvicorn', 'api:app', '--app-dir', 'backend/src', '--port', "$PORT_API" `
        -WorkingDirectory $racine -PassThru -WindowStyle Hidden

    if (-not (Attendre-Url "http://127.0.0.1:$PORT_API/api/health" 40 "L'API")) {
        Arreter-Arbre $api
        Read-Host "Entree pour fermer"
        exit 1
    }
    Ecrire "  API prete sur http://127.0.0.1:$PORT_API" 'Green'

    Ecrire "Demarrage de l'interface..." 'Gray'
    $ui = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' `
        -WorkingDirectory $frontend -PassThru -WindowStyle Hidden

    if (-not (Attendre-Url "http://localhost:$PORT_UI/" 90 "L'interface")) {
        Arreter-Arbre $ui
        Arreter-Arbre $api
        Read-Host "Entree pour fermer"
        exit 1
    }
    Ecrire "  Interface prete sur http://localhost:$PORT_UI" 'Green'

    Start-Process "http://localhost:$PORT_UI"

    Ecrire ""
    Ecrire "L'application tourne. http://localhost:$PORT_UI" 'Cyan'
    Ecrire "GARDEZ CETTE FENETRE OUVERTE : la fermer arrete l'application." 'Yellow'
    Ecrire "Ctrl+C pour arreter proprement." 'Gray'
    Ecrire ""

    # Surveillance : si l'un des deux meurt de son cote, on le dit et on arrete
    # l'autre, plutot que de laisser une moitie d'application en marche.
    while ($true) {
        Start-Sleep -Seconds 2
        if ($api.HasExited) { Ecrire "L'API s'est arretee." 'Red'; break }
        if ($ui.HasExited)  { Ecrire "L'interface s'est arretee." 'Red'; break }
    }
}
finally {
    Ecrire ""
    Ecrire "Arret en cours..." 'Gray'
    Arreter-Arbre $ui
    Arreter-Arbre $api
    Ecrire "Arrete." 'Green'
    Start-Sleep -Seconds 1
}
