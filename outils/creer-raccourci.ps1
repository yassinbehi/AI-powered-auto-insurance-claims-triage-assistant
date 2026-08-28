<#
    outils/creer-raccourci.ps1 — pose un raccourci "TSA" sur le Bureau.

    A executer UNE SEULE FOIS. Le raccourci pointe sur lancer.bat, avec le
    dossier du projet comme repertoire de travail : il fonctionne donc quel
    que soit l'endroit d'ou on le double-clique.
#>

$ErrorActionPreference = 'Stop'

$racine = Split-Path -Parent $PSScriptRoot
$cible = Join-Path $racine 'lancer.bat'

if (-not (Test-Path $cible)) {
    Write-Host "lancer.bat introuvable a la racine du projet." -ForegroundColor Red
    exit 1
}

$bureau = [Environment]::GetFolderPath('Desktop')
$raccourci = Join-Path $bureau 'TSA - Triage Sinistres Auto.lnk'

$shell = New-Object -ComObject WScript.Shell
$lien = $shell.CreateShortcut($raccourci)
$lien.TargetPath = $cible
$lien.WorkingDirectory = $racine
$lien.Description = "Demarre l'API et l'interface du triage des sinistres auto"
# Icone : une du systeme, faute d'icone propre au projet. Pour en changer,
# remplacez cette ligne par le chemin d'un fichier .ico.
$lien.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
$lien.Save()

Write-Host "Raccourci cree :" -ForegroundColor Green
Write-Host "  $raccourci"
Write-Host ""
Write-Host "Double-cliquez-le pour demarrer l'application."
Write-Host "La fenetre qui s'ouvre doit rester ouverte : la fermer arrete tout."
