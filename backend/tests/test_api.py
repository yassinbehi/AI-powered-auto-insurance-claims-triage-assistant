"""Tests de la couche HTTP (src/api.py).

AUCUN APPEL API. Deux mecanismes garantissent que ces tests restent hors
ligne :

  - une fixture autouse remplace anthropic.Anthropic par un objet qui leve
    des l'instanciation : toute tentative de contacter le modele echoue
    bruyamment au lieu de partir sur le reseau ;
  - les endpoints payants sont testes avec agent.triage_claim et
    guard.classify_client_text remplaces par des doublures.

Les endpoints gratuits, eux, sont exerces pour de vrai contre les CSV de
data/ : c'est justement ce qui doit fonctionner sans cle API.
"""

import csv
import io
import json
import uuid

import pytest
from fastapi.testclient import TestClient

import agent
import api
import dataset
import dataset_db
import guard
import tools
import urgence
from api import app
from config import CLAIMS_FILE, POLICIES_FILE
from tools import list_claim_ids, parse_claims_csv, parse_policies_csv

client = TestClient(app)


def _texte(chemin):
    # Passe par tools.lire_csv et non par read_text(encoding="utf-8") : les
    # CSV de data/ peuvent avoir ete reenregistres depuis un editeur Windows,
    # donc en cp1252. Les tests doivent lire ce que l'application lit.
    return tools.lire_csv(chemin)


def _declarations_utilisateur() -> str:
    """Un fichier de declarations tel qu'un utilisateur en fournit.

    Reprend la structure du jeu d'essai, colonnes de reponses attendues
    comprises - c'est ce qu'on obtient en partant de data/claims_auto.csv
    comme gabarit - mais avec d'autres recits. Sert a verifier que le depot
    fonctionne sur un fichier quelconque, sans que rien dans son contenu ni
    dans son nom n'entre en ligne de compte.
    """
    lecteur = csv.reader(io.StringIO(_texte(CLAIMS_FILE)))
    colonnes = next(lecteur)
    i_description = colonnes.index("description_client")

    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, lineterminator="\n")
    ecrivain.writerow(colonnes)
    for numero, ligne in enumerate(lecteur, start=1):
        if not ligne:
            continue  # ligne vide de fin de fichier
        ligne[i_description] = f"Recit du dossier numero {numero}."
        ecrivain.writerow(ligne)
    return sortie.getvalue()


def _sans_colonnes_de_reponses(texte: str) -> str:
    """Le meme fichier prive de priorite_attendue et triage_attendu."""
    lecteur = csv.reader(io.StringIO(texte))
    colonnes = next(lecteur)
    gardees = [
        i for i, colonne in enumerate(colonnes)
        if colonne not in tools.EVAL_LABEL_COLUMNS
    ]
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, lineterminator="\n")
    ecrivain.writerow([colonnes[i] for i in gardees])
    for ligne in lecteur:
        if not ligne:
            continue
        ecrivain.writerow([ligne[i] if i < len(ligne) else "" for i in gardees])
    return sortie.getvalue()


def _remplacer_valeur(texte: str, claim_id: str, colonne: str, valeur: str) -> str:
    """Reecrit une seule cellule d'un CSV de declarations.

    Sert a fabriquer les defauts de mise en forme qu'un tableur produit
    reellement, a partir du jeu d'essai plutot que d'un fichier invente.
    """
    lecteur = csv.reader(io.StringIO(texte))
    colonnes = next(lecteur)
    i_id = colonnes.index("claim_id")
    i_colonne = colonnes.index(colonne)

    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, lineterminator="\n")
    ecrivain.writerow(colonnes)
    for ligne in lecteur:
        if not ligne:
            continue  # ligne vide de fin de fichier
        if ligne[i_id] == claim_id:
            ligne[i_colonne] = valeur
        ecrivain.writerow(ligne)
    return sortie.getvalue()


def charger_jeu_de_donnees():
    """Charge les CSV de data/ comme s'ils avaient ete deposes par
    l'utilisateur.

    C'est le SEUL usage legitime de ces fichiers ici : ce sont des jeux
    d'essai. L'application, elle, n'a de donnees que si quelqu'un en depose.
    """
    dataset.set_active(
        parse_claims_csv(_texte(CLAIMS_FILE)).lignes,
        parse_policies_csv(_texte(POLICIES_FILE)).lignes,
        source=dataset.SOURCE_DEPOT,
        claims_filename="claims_auto.csv",
        policies_filename="policies_auto.csv",
        # Obligatoire depuis que les jeux sont nommes : set_active refuse un
        # depot sans nom, comme le ferait l'API.
        nom="Jeu d'essai",
    )


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Filet de securite : aucun test de ce fichier ne doit pouvoir construire
    un vrai client Anthropic. Charge aussi un jeu de donnees, sans lequel
    l'API refuse de repondre."""

    def _forbidden(*args, **kwargs):
        raise AssertionError(
            "Un test de test_api.py a tente de creer un client Anthropic : "
            "un appel de modele s'est glisse dans un chemin cense etre gratuit."
        )

    monkeypatch.setattr(guard.anthropic, "Anthropic", _forbidden)
    guard.reset_screening_cache()
    guard.reset_guard_usage()
    # Base videe avant chaque test : les noms de jeux sont uniques, et
    # dataset.clear() ne fait que FERMER le jeu actif sans le supprimer. Sans
    # ce vidage, le deuxieme test du fichier redeposerait le meme nom et
    # recevrait NomDejaPris. (La base pointe deja sur un fichier temporaire,
    # voir la fixture base_a_l_ecart de conftest.py.)
    dataset_db.clear()
    charger_jeu_de_donnees()
    yield
    dataset.clear()
    dataset_db.clear()
    guard.reset_screening_cache()
    guard.reset_guard_usage()


def _parse_sse(text: str) -> list:
    """Decoupe une reponse text/event-stream en couples (evenement, donnees).
    Les commentaires de heartbeat (`: ping`) sont ignores."""
    frames = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(":"):
            continue
        event = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        frames.append((event, data))
    return frames


# =============================================================================
# Jeu de donnees depose par l'utilisateur
# =============================================================================

class TestSansJeuDeDonnees:
    """Tant que rien n'a ete depose, l'application n'a AUCUNE donnee.

    Le piege a eviter est le repli silencieux sur les CSV de data/ : le
    gestionnaire croirait travailler sur ses dossiers alors qu'il regarderait
    les jeux d'essai des evaluations.
    """

    def test_etat_vide(self):
        dataset.clear()
        body = client.get("/api/dataset").json()
        assert body["loaded"] is False
        assert body["claims_count"] is None

    @pytest.mark.parametrize(
        "methode,url",
        [
            ("get", "/api/claims"),
            ("get", "/api/claims/CLM-001"),
            ("get", "/api/policies/POL-002"),
            ("post", "/api/claims/CLM-001/screen"),
            ("post", "/api/triage/CLM-001"),
            ("get", "/api/triage/CLM-001/stream?confirm=1"),
        ],
    )
    def test_tout_est_refuse(self, methode, url):
        dataset.clear()
        reponse = getattr(client, methode)(url)
        assert reponse.status_code == 409
        assert "depose" in reponse.json()["detail"]

    def test_aucun_repli_sur_les_fichiers_du_depot(self):
        dataset.clear()
        # Les CSV de data/ existent bel et bien : si l'API repondait, c'est
        # qu'elle s'y serait rabattue.
        assert CLAIMS_FILE.exists() and POLICIES_FILE.exists()
        assert client.get("/api/claims").status_code == 409

    def test_un_jeu_lu_sur_le_disque_n_est_jamais_servi(self):
        """Le scenario redoute : un appel a load_dataset_from_files() se
        glisse dans le processus du serveur (import, script, mauvaise
        manipulation). Les jeux d'essai sont alors bel et bien en memoire, et
        l'application doit malgre tout se comporter comme si elle etait vide -
        sinon le gestionnaire verrait 8 sinistres de test a la place de ses
        dossiers."""
        dataset.clear()
        tools.load_dataset_from_files()
        assert dataset.is_loaded() is True

        assert client.get("/api/dataset").json()["loaded"] is False
        assert client.get("/api/claims").status_code == 409
        assert client.get("/api/claims/CLM-001").status_code == 409
        assert client.post("/api/triage/CLM-001").status_code == 409

    def test_le_verrou_de_triage_n_est_pas_pris(self):
        dataset.clear()
        client.post("/api/triage/CLM-001")
        assert not api._RUN_LOCK.locked()


class TestDepotDesFichiers:
    def _deposer(self, claims_text=None, policies_text=None):
        return client.post(
            "/api/dataset",
            # `nom` est obligatoire depuis que les jeux sont nommes.
            data={"nom": f"Jeu {uuid.uuid4().hex[:8]}"},
            files={
                "claims_file": (
                    "mes_declarations.csv",
                    claims_text if claims_text is not None
                    else _declarations_utilisateur(),
                    "text/csv",
                ),
                "policies_file": (
                    "mes_contrats.csv",
                    policies_text if policies_text is not None else _texte(POLICIES_FILE),
                    "text/csv",
                ),
            },
        )

    def test_depot_complet(self):
        dataset.clear()
        body = self._deposer().json()
        assert body["loaded"] is True
        assert body["claims_count"] == 8
        assert body["policies_count"] == 8
        assert body["claims_filename"] == "mes_declarations.csv"

    def test_les_donnees_deposees_sont_servies(self):
        dataset.clear()
        self._deposer()
        assert len(client.get("/api/claims").json()) == 8

    def test_colonnes_manquantes_refusees(self):
        dataset.clear()
        reponse = self._deposer(claims_text="claim_id,policy_id\nCLM-001,POL-002\n")
        assert reponse.status_code == 422
        assert "colonnes manquantes" in reponse.json()["detail"]
        assert dataset.is_loaded() is False, "un fichier refuse ne doit rien charger"

    def test_fichier_vide_refuse(self):
        dataset.clear()
        entetes = ",".join(
            [
                "claim_id", "policy_id", "date_sinistre", "type_sinistre",
                "description_client", "blessure", "constat", "photos",
                "devis_tnd", "tiers_identifie", "kilometrage_declare",
            ]
        )
        reponse = self._deposer(claims_text=entetes + "\n")
        assert reponse.status_code == 422

    def test_aucun_filtre_sur_le_contenu(self):
        """L'API n'inspecte pas ce que contiennent les lignes.

        Une version precedente reconnaissait le jeu d'essai de data/ et
        refusait le depot. C'etait une erreur de perimetre : la regle du
        projet veut que le systeme n'aille jamais chercher data/ tout seul,
        pas qu'il juge les fichiers qu'on lui donne. Meme le jeu d'essai,
        depose deliberement, doit etre charge et servi."""
        dataset.clear()
        body = self._deposer(claims_text=_texte(CLAIMS_FILE)).json()
        assert body["loaded"] is True
        assert body["claims_count"] == 8
        assert len(client.get("/api/claims").json()) == 8

    @pytest.mark.parametrize(
        "nom", ["claims_auto.csv", "dossiers.csv", "export final (2).CSV", "a"]
    )
    def test_aucun_filtre_sur_le_nom_du_fichier(self, nom):
        """Le nom n'entre dans aucune decision : il n'est conserve que pour
        etre reaffiche a l'utilisateur."""
        dataset.clear()
        reponse = client.post(
            "/api/dataset",
            data={"nom": f"Jeu {uuid.uuid4().hex[:8]}"},
            files={
                "claims_file": (nom, _declarations_utilisateur(), "text/csv"),
                "policies_file": ("x", _texte(POLICIES_FILE), "text/csv"),
            },
        )
        assert reponse.status_code == 200
        assert reponse.json()["claims_filename"] == nom

    def test_les_reponses_attendues_restent_retirees_a_la_lecture(self):
        """Le depot n'est plus filtre, mais les colonnes de verite terrain ne
        ressortent toujours pas : c'est _claims_from_rows qui le garantit, en
        ne recopiant que les colonnes metier."""
        dataset.clear()
        self._deposer(claims_text=_texte(CLAIMS_FILE))
        brut = json.dumps(client.get("/api/claims/CLM-001").json(), ensure_ascii=False)
        assert "priorite_attendue" not in brut
        assert "triage_attendu" not in brut

    def test_les_reponses_attendues_sont_retirees_a_l_import(self):
        """Deuxieme ligne de defense, au niveau du parseur.

        Le depot refuse deja ces fichiers, mais parse_claims_csv sert aussi
        aux outils en terminal : la garantie que ces colonnes ne sortent pas
        de la lecture doit tenir independamment de l'endpoint."""
        lu = parse_claims_csv(_texte(CLAIMS_FILE))
        brut = json.dumps(lu.lignes, ensure_ascii=False)
        assert "priorite_attendue" not in brut
        assert "triage_attendu" not in brut

    def test_declarations_sans_contrat_signalees(self):
        dataset.clear()
        contrats = _texte(POLICIES_FILE).splitlines()
        # Ne garde que l'entete et la premiere police.
        tronque = "\n".join(contrats[:2]) + "\n"
        body = self._deposer(policies_text=tronque).json()
        assert body["loaded"] is True
        assert len(body["claims_sans_contrat"]) > 0

    def test_remplacement_vide_le_memo_de_screening(self):
        """Le screening est memorise par claim_id. Sans vidage, un nouveau
        fichier reutiliserait les verdicts calcules sur l'ancien."""
        dataset.clear()
        self._deposer()
        client.get("/api/claims/CLM-002")  # remplit eventuellement le memo
        guard._screening_cache["CLM-002"] = {"verdict": "SAFE"}
        self._deposer()
        assert "CLM-002" not in guard._screening_cache

    def test_suppression(self):
        dataset.clear()
        self._deposer()
        assert client.delete("/api/dataset").json()["loaded"] is False
        assert client.get("/api/claims").status_code == 409


class TestCORS:
    """Le navigateur demande l'autorisation AVANT d'envoyer une requete non
    triviale. Une methode absente de allow_methods ne produit aucune erreur
    cote serveur : la requete ne part tout simplement jamais, et l'interface
    n'a qu'un "TypeError: Failed to fetch" a montrer. Le retrait du jeu de
    donnees (DELETE) a echoue ainsi pendant que le meme appel passait en curl.
    """

    @pytest.mark.parametrize("methode", ["GET", "POST", "DELETE"])
    def test_le_preflight_autorise_les_methodes_du_client(self, methode):
        reponse = client.options(
            "/api/dataset",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": methode,
            },
        )
        assert reponse.status_code == 200, (
            f"{methode} /api/dataset est appele par le navigateur mais refuse "
            f"au preflight : ajoutez-le a allow_methods dans api.py"
        )
        autorisees = reponse.headers.get("access-control-allow-methods", "")
        assert methode in autorisees

    def test_l_origine_du_frontend_est_autorisee(self):
        reponse = client.get("/api/dataset", headers={"Origin": "http://localhost:3000"})
        assert reponse.headers.get("access-control-allow-origin") == "http://localhost:3000"


class TestLignesRejetees:
    """Une ligne fournie par l'utilisateur ne disparait plus en silence.

    Le defaut d'origine : les parseurs ignoraient toute ligne qu'ils
    n'arrivaient pas a lire. Un montant ecrit "2 400" par un tableur suffisait
    a effacer un dossier, l'en-tete etant correct le depot repondait 200, et
    l'utilisateur n'avait aucun moyen d'apprendre que sa ligne avait ete jetee.
    """

    def _deposer(self, claims_text):
        return client.post(
            "/api/dataset",
            data={"nom": f"Jeu {uuid.uuid4().hex[:8]}"},
            files={
                "claims_file": ("mes_declarations.csv", claims_text, "text/csv"),
                "policies_file": ("mes_contrats.csv", _texte(POLICIES_FILE), "text/csv"),
            },
        )

    def test_espace_de_tableur_ne_fait_plus_disparaitre_la_ligne(self):
        """Cas exact du bug : un espace insecable dans un montant."""
        dataset.clear()
        texte = _remplacer_valeur(
        # "2\u00a0400" : espace INSECABLE, celui qu'un tableur insere tout
        # seul. Ecrit en echappement parce qu'il est invisible en source,
        # exactement comme il l'etait dans le fichier de l'utilisateur.
            _declarations_utilisateur(), "CLM-001", "devis_tnd", "2\u00a0400"
        )
        body = self._deposer(texte).json()

        assert body["claims_count"] == 8, "aucune ligne ne doit manquer"
        assert body["lignes_rejetees"] == []
        assert client.get("/api/claims/CLM-001").json()["claim"]["devis_tnd"] == 2400

    def test_valeur_illisible_est_signalee_et_non_supprimee(self):
        dataset.clear()
        texte = _remplacer_valeur(
            _declarations_utilisateur(), "CLM-001", "devis_tnd", "N/A"
        )
        body = self._deposer(texte).json()

        # La ligne reste inexploitable - on ne devine pas un montant - mais
        # elle est NOMMEE, ce qui est toute la difference.
        assert body["claims_count"] == 7
        assert len(body["lignes_rejetees"]) == 1
        rejet = body["lignes_rejetees"][0]
        assert rejet["fichier"] == "declarations"
        assert rejet["ligne"] == 2, "numero de ligne du tableur, en-tete compris"
        assert rejet["identifiant"] == "CLM-001"
        assert "devis_tnd" in rejet["raison"]

    def test_les_rejets_survivent_au_rafraichissement(self):
        """L'interface se rafraichit en relisant /api/dataset. Un
        avertissement rendu seulement dans la reponse au depot disparaitrait
        au premier rafraichissement, donc ne previendrait personne."""
        dataset.clear()
        texte = _remplacer_valeur(
            _declarations_utilisateur(), "CLM-003", "kilometrage_declare", "beaucoup"
        )
        self._deposer(texte)
        assert len(client.get("/api/dataset").json()["lignes_rejetees"]) == 1

    def test_claim_id_en_double_est_signale(self):
        """Deux lignes de meme identifiant : la seconde ecrasait la premiere
        sans un mot."""
        dataset.clear()
        texte = _declarations_utilisateur()
        lignes = texte.splitlines()
        doublon = "\n".join(lignes + [lignes[1]]) + "\n"
        body = self._deposer(doublon).json()

        assert body["claims_count"] == 8
        assert any("double" in r["raison"] for r in body["lignes_rejetees"])

    def test_fichier_entierement_illisible_explique_pourquoi(self):
        """Quand plus rien n'est lisible, le 422 doit nommer la cause :
        "aucune declaration exploitable" tout seul ne dit pas ou regarder."""
        dataset.clear()
        texte = _declarations_utilisateur()
        for claim_id in [f"CLM-00{n}" for n in range(1, 9)]:
            texte = _remplacer_valeur(texte, claim_id, "devis_tnd", "N/A")

        reponse = self._deposer(texte)
        assert reponse.status_code == 422
        assert "devis_tnd" in reponse.json()["detail"]
        assert dataset.is_loaded() is False


# =============================================================================
# Endpoints gratuits
# =============================================================================

class TestEndpointsGratuits:
    def test_health(self):
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["model"]

    def test_file_d_attente_liste_tous_les_sinistres(self):
        response = client.get("/api/claims")
        assert response.status_code == 200
        assert len(response.json()) == len(list_claim_ids())

    def test_file_d_attente_joint_la_police(self):
        row = next(c for c in client.get("/api/claims").json() if c["claim_id"] == "CLM-001")
        assert row["assure"], "la file doit etre lisible sans ouvrir le dossier"
        assert row["formule"]

    def test_fiche_dossier_complete(self):
        body = client.get("/api/claims/CLM-001").json()
        assert set(body) == {
            "claim", "policy", "coverage", "repair_band", "fraud_signals", "screening",
        }
        assert body["claim"]["claim_id"] == "CLM-001"
        assert body["policy"]["policy_id"] == body["claim"]["policy_id"]

    def test_fiche_dossier_ne_declenche_aucun_appel_de_modele(self, monkeypatch):
        # Complete la fixture _no_network : ici c'est la couche [2] elle-meme
        # qui doit rester intouchee, meme si un client existait deja.
        def _forbidden(*args, **kwargs):
            raise AssertionError("la couche [2] ne doit pas etre appelee ici")

        monkeypatch.setattr(guard, "_call_classifier", _forbidden)
        for claim_id in list_claim_ids():
            assert client.get(f"/api/claims/{claim_id}").status_code == 200

    def test_police_seule(self):
        assert client.get("/api/policies/POL-002").json()["formule"] == "tous_risques"

    def test_regles_servies_telles_quelles(self):
        documents = client.get("/api/rules").json()["documents"]
        noms = {d["name"] for d in documents}
        assert noms == {"regles_sinistres.md", "contrat_sortie.md"}
        assert all(d["content"].strip() for d in documents)

    def test_sinistre_inconnu(self):
        assert client.get("/api/claims/CLM-999").status_code == 404

    def test_police_inconnue(self):
        assert client.get("/api/policies/POL-999").status_code == 404


# =============================================================================
# Urgence estimee dans la file
# =============================================================================

class TestUrgenceDansLaFile:
    """src/urgence.py, vu depuis HTTP.

    Le bareme lui-meme est teste dans test_urgence.py. Ce qui se joue ici,
    c'est qu'il traverse la couche HTTP intact et qu'il reste ce qu'il pretend
    etre : un repere de lecture gratuit, et NON la `priorite` de l'agent.
    """

    def test_chaque_ligne_porte_une_urgence_lisible(self):
        for row in client.get("/api/claims").json():
            assert row["urgence_estimee"] in urgence.NIVEAUX
            assert isinstance(row["urgence_motifs"], list)

    def test_la_fiche_dossier_n_expose_pas_l_urgence(self):
        # Non-objectif explicite : la fiche a ses propres panneaux, et
        # test_fiche_dossier_complete fige deja l'ensemble exact de ses cles.
        body = client.get("/api/claims/CLM-001").json()
        assert "urgence_estimee" not in body

    def test_valeurs_figees_sur_le_jeu_d_essai(self):
        """Test de CARACTERISATION : fige ce que le bareme donne aujourd'hui.

        Il n'affirme pas que ces valeurs sont les bonnes - une partie du
        bareme est deduite, donc discutable (voir urgence.py). Il affirme
        qu'on ne les changera pas sans s'en apercevoir.

        TROIS DIVERGENCES AVEC priorite_attendue SONT ATTENDUES. Ne pas les
        "corriger" : ce sont deux grandeurs differentes, et c'est precisement
        pour cela que l'interface ne leur donne ni les memes mots ni la meme
        forme.

          CLM-002  haute vs normale  - le message client porte des marqueurs
                   d'injection. La file remonte le dossier parce qu'un humain
                   doit regarder ce texte ; l'agent, lui, l'ecarte et conclut
                   sur le reste.
          CLM-006  haute vs normale  - meme cas.
          CLM-004  normale vs haute  - vol sans devis chiffre. Le `haute` de
                   l'eval vient des pieces manquantes d'un vol (depot de
                   plainte, carte grise, cles, declaration circonstanciee) :
                   aucune de ces quatre pieces n'est une colonne du CSV, donc
                   la file ne peut pas le savoir gratuitement.
        """
        attendu = {
            "CLM-001": ("normale", []),
            "CLM-002": ("haute", ["message_client_signale"]),
            "CLM-003": ("haute", ["devis_au_dessus_du_seuil"]),
            "CLM-004": ("normale", ["montant_inconnu"]),
            "CLM-005": ("critique", ["blessure_declaree", "devis_au_dessus_du_seuil"]),
            "CLM-006": ("haute", ["message_client_signale"]),
            "CLM-007": ("haute", ["devis_au_dessus_du_seuil"]),
            "CLM-008": ("normale", []),
        }
        obtenu = {
            row["claim_id"]: (row["urgence_estimee"], row["urgence_motifs"])
            for row in client.get("/api/claims").json()
        }
        assert obtenu == attendu

    def test_l_urgence_ne_coute_aucun_appel_de_modele(self, monkeypatch):
        def _forbidden(*args, **kwargs):
            raise AssertionError("la file ne doit declencher aucun appel de modele")

        monkeypatch.setattr(guard, "_call_classifier", _forbidden)
        assert client.get("/api/claims").status_code == 200


# =============================================================================
# Point de vigilance 1 : les colonnes de reference ne sortent jamais
# =============================================================================

class TestFuiteDesReponsesAttendues:
    """claims_auto.csv contient priorite_attendue et triage_attendu, qui sont
    les reponses attendues des evals. Les exposer par HTTP rendrait toute
    mesure de qualite sans valeur."""

    INTERDIT = ("priorite_attendue", "triage_attendu")

    def _assert_propre(self, payload):
        brut = json.dumps(payload, ensure_ascii=False)
        for colonne in self.INTERDIT:
            assert colonne not in brut, f"{colonne} ne doit jamais sortir par HTTP"

    def test_file_d_attente(self):
        self._assert_propre(client.get("/api/claims").json())

    def test_chaque_fiche_dossier(self):
        for claim_id in list_claim_ids():
            self._assert_propre(client.get(f"/api/claims/{claim_id}").json())

    def test_le_module_api_n_importe_pas_le_lecteur_de_labels(self):
        # get_claim_eval_labels est la seule fonction qui lit ces colonnes.
        assert not hasattr(api, "get_claim_eval_labels")


# =============================================================================
# Filtre anti-injection expose par l'API
# =============================================================================

class TestScreeningExpose:
    def test_absence_de_verdict_sur_la_fiche_gratuite(self):
        # CLM-001 : aucun marqueur connu. Sans la couche [2], il n'y a pas de
        # verdict - et surtout pas un SAFE fabrique.
        screening = client.get("/api/claims/CLM-001").json()["screening"]
        assert screening["verdict"] is None
        assert screening["classifier_called"] is False
        assert screening["redacted"] is False

    def test_injection_detectee_sans_appel_de_modele(self):
        # CLM-002 contient "approuver le paiement" / "sans verifier" : la
        # couche [1] tranche seule, gratuitement.
        screening = client.get("/api/claims/CLM-002").json()["screening"]
        assert screening["verdict"] == "INJECTION"
        assert screening["markers_found"]
        assert screening["classifier_called"] is False
        assert screening["redacted"] is True

    def test_texte_injecte_lisible_par_l_humain_mais_pas_par_le_modele(self):
        """Le texte du client est expose pour LECTURE HUMAINE
        (screening.original_text), mais ne franchit jamais la frontiere du
        MODELE : text_for_model et description_client restent le placeholder.

        A ne pas confondre avec `markers_found`, qui sort aussi : ses entrees
        proviennent de guard.INJECTION_MARKERS, un vocabulaire fixe du depot,
        et non de ce que le client a ecrit. C'est la trace du filtre.
        """
        body = client.get("/api/claims/CLM-002").json()

        # Cote humain : le texte brut du client est lisible tel quel. Phrases
        # propres a CLM-002 dans claims_auto.csv.
        original = body["screening"]["original_text"]
        assert "Pare-brise fissure sur autoroute" in original
        assert "sans verifier la police" in original

        # Cote modele : rien du texte brut ne transparait. Le triage ne voit
        # que le placeholder, aussi bien dans le screening que dans le claim.
        assert body["screening"]["text_for_model"] == guard.REDACTED_PLACEHOLDER
        assert body["claim"]["description_client"] == guard.REDACTED_PLACEHOLDER
        assert set(body["screening"]["markers_found"]) <= set(guard.INJECTION_MARKERS)

    def test_marqueurs_signales_dans_la_file(self):
        rows = {c["claim_id"]: c for c in client.get("/api/claims").json()}
        assert rows["CLM-002"]["injection_markers_found"]
        assert rows["CLM-006"]["injection_markers_found"]
        assert rows["CLM-001"]["injection_markers_found"] == []

    def test_consultation_gratuite_ne_pollue_pas_le_memo(self, monkeypatch):
        """Une fiche consultee sans classifieur ne doit pas empecher le triage
        suivant d'executer la couche [2] sur le meme sinistre."""
        assert client.get("/api/claims/CLM-001").status_code == 200

        appels = []

        def _doublure(text, client=None, use_classifier=True):
            appels.append(use_classifier)
            return {
                "verdict": "SAFE",
                "markers_found": [],
                "classifier_available": True,
                "classifier_called": True,
                "text_for_model": guard.wrap_untrusted(text),
                "original_text": text,
            }

        monkeypatch.setattr(guard, "classify_client_text", _doublure)

        body = client.post("/api/claims/CLM-001/screen").json()
        assert body["verdict"] == "SAFE"
        assert appels == [True], "la couche [2] doit bien avoir ete sollicitee"


# =============================================================================
# Point de vigilance 2 : serialisation du travail payant
# =============================================================================

class TestVerrou:
    def test_second_triage_refuse(self):
        api._RUN_LOCK.acquire()
        try:
            assert client.post("/api/triage/CLM-001").status_code == 409
            assert client.post("/api/claims/CLM-001/screen").status_code == 409
        finally:
            api._RUN_LOCK.release()

    def test_verrou_libere_apres_un_triage(self, monkeypatch):
        monkeypatch.setattr(
            agent, "triage_claim",
            # **kwargs : l'API passe desormais `model` (selecteur de modele).
            lambda claim_id, client=None, on_event=None, **kwargs: {
                "claim_id": claim_id, "output": {}
            },
        )
        assert client.post("/api/triage/CLM-001").status_code == 200
        assert not api._RUN_LOCK.locked(), "le verrou doit etre rendu"

    def test_sinistre_inconnu_ne_prend_pas_le_verrou(self):
        assert client.post("/api/triage/CLM-999").status_code == 404
        assert not api._RUN_LOCK.locked()


# =============================================================================
# Point de vigilance 3 : un GET ne declenche pas un triage par accident
# =============================================================================

class TestGardeFouSSE:
    def test_confirm_obligatoire(self):
        assert client.get("/api/triage/CLM-001/stream").status_code == 400
        assert client.get("/api/triage/CLM-001/stream?confirm=0").status_code == 400

    def test_confirm_refuse_ne_prend_pas_le_verrou(self):
        client.get("/api/triage/CLM-001/stream")
        assert not api._RUN_LOCK.locked()

    def test_sinistre_inconnu_avant_tout_lancement(self):
        assert client.get("/api/triage/CLM-999/stream?confirm=1").status_code == 404


# =============================================================================
# Forme des trames SSE
# =============================================================================

def _triage_scripte(claim_id, client=None, on_event=None, **kwargs):
    """Doublure de agent.triage_claim : rejoue une sequence d'evenements
    representative d'un triage reel, sans appel de modele."""
    resultat = {
        "claim_id": claim_id,
        "output": {"claim_id": claim_id, "triage": "traitement_standard"},
        "validation_errors": [],
        "tool_call_trace": [],
        "usage": {"input_tokens": 10, "output_tokens": 2},
    }
    on_event({"type": "run_started", "claim_id": claim_id, "model": "doublure"})
    on_event({"type": "turn_started", "turn": 1})
    on_event({"type": "tool_use", "turn": 1, "tool": "get_claim", "input": {"claim_id": claim_id}})
    on_event({"type": "tool_result", "turn": 1, "tool": "get_claim", "output": {"claim_id": claim_id}})
    on_event({"type": "turn_completed", "turn": 1, "usage": {"input_tokens": 10}})
    on_event({"type": "turn_started", "turn": 2})
    # Un JSON contenant un retour a la ligne : il ne doit pas couper la trame.
    on_event({"type": "text_delta", "text": '{\n  "claim_id"'})
    on_event({"type": "result", **resultat})
    return resultat


class TestFluxSSE:
    def _frames(self, monkeypatch, claim_id="CLM-001"):
        monkeypatch.setattr(agent, "triage_claim", _triage_scripte)
        response = client.get(f"/api/triage/{claim_id}/stream?confirm=1")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return _parse_sse(response.text)

    def test_sequence_complete(self, monkeypatch):
        noms = [nom for nom, _ in self._frames(monkeypatch)]
        assert noms == [
            "stream_open", "run_started", "turn_started", "tool_use", "tool_result",
            "turn_completed", "turn_started", "text_delta", "result", "done",
        ]

    def test_le_resultat_transporte_le_contrat_de_sortie(self, monkeypatch):
        frames = dict(self._frames(monkeypatch))
        assert frames["result"]["output"]["triage"] == "traitement_standard"
        assert frames["result"]["validation_errors"] == []

    def test_un_retour_a_la_ligne_ne_coupe_pas_la_trame(self, monkeypatch):
        frames = dict(self._frames(monkeypatch))
        assert frames["text_delta"]["text"] == '{\n  "claim_id"'

    def test_le_type_n_est_pas_duplique_dans_les_donnees(self, monkeypatch):
        # Le type est porte par la ligne `event:` ; le repeter dans `data:`
        # obligerait le frontend a choisir entre deux sources.
        for _, data in self._frames(monkeypatch):
            assert "type" not in data

    def test_verrou_libere_en_fin_de_flux(self, monkeypatch):
        self._frames(monkeypatch)
        assert not api._RUN_LOCK.locked()

    def test_une_exception_du_triage_est_remontee_puis_le_flux_se_ferme(self, monkeypatch):
        def _explose(claim_id, client=None, on_event=None, **kwargs):
            raise RuntimeError("panne simulee")

        monkeypatch.setattr(agent, "triage_claim", _explose)
        frames = _parse_sse(client.get("/api/triage/CLM-001/stream?confirm=1").text)
        noms = [nom for nom, _ in frames]
        # "run_error" et non "error" : voir _EVENT_NAME_OVERRIDES (collision
        # avec l'evenement de transport d'EventSource cote navigateur).
        assert noms == ["stream_open", "run_error", "done"]
        assert "panne simulee" in dict(frames)["run_error"]["message"]
        assert not api._RUN_LOCK.locked(), "meme en cas d'echec, le verrou est rendu"

    def test_l_evenement_error_de_l_agent_est_renomme(self, monkeypatch):
        def _sans_json(claim_id, client=None, on_event=None, **kwargs):
            on_event({"type": "error", "message": "pas un JSON", "raw_output": "desole"})
            return {"claim_id": claim_id, "error": "pas un JSON"}

        monkeypatch.setattr(agent, "triage_claim", _sans_json)
        frames = _parse_sse(client.get("/api/triage/CLM-001/stream?confirm=1").text)
        noms = [nom for nom, _ in frames]
        assert "run_error" in noms
        assert "error" not in noms
        assert dict(frames)["run_error"]["raw_output"] == "desole"
