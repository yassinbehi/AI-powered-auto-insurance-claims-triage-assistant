@echo off
rem ---------------------------------------------------------------------------
rem lancer.bat - point d'entree double-cliquable de l'application TSA.
rem
rem Ne fait qu'appeler outils\lancer.ps1, qui contient toute la logique.
rem -ExecutionPolicy Bypass : ne modifie AUCUN reglage de la machine, la
rem derogation ne vaut que pour ce lancement-ci.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0outils\lancer.ps1"
if errorlevel 1 pause
