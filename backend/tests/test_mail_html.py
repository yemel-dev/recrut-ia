"""Version mise en forme des mails aux candidats : contenu échappé, encadré de l'entretien, bouton de la visio."""
from __future__ import annotations

import email
from email import policy

from backend.services import mail_html
from backend.services.expediteur import MailSortant, construire_mime

CORPS = (
    "Bonjour Awa Ndong,\n\nNous vous proposons un entretien le lundi 12 octobre 2026 à 10 h 00.\n\n"
    "Lien : https://meet.injara.site/public/entretien/abc123.\n\nCordialement,\nCabinet <Ndong> & Fils"
)


def test_texte_echappe_liens_cliquables_et_signature():
    rendu = mail_html.rendre(CORPS, mail_html.Signature(nom="Cabinet <Ndong> & Fils", ville="Douala", telephone="+237 6 00"), objet="Invitation")
    assert "Cabinet &lt;Ndong&gt; &amp; Fils" in rendu and "<Ndong>" not in rendu
    assert 'href="https://meet.injara.site/public/entretien/abc123"' in rendu  # le point final n'est pas dans le lien
    assert "Cordialement,<br>" in rendu and "Douala · +237 6 00" in rendu
    assert "<img" not in rendu and "src=" not in rendu  # aucune ressource externe


def test_encadre_de_l_entretien_apres_la_date_et_bouton_de_visio():
    entretien = mail_html.Entretien(
        date="lundi 12 octobre 2026", heure="10 h 00", duree="1 heure", lieu="En ligne (visioconférence)", lien="https://meet.injara.site/x"
    )
    rendu = mail_html.rendre(CORPS, mail_html.Signature(nom="Cabinet Ndong"), entretien)
    assert rendu.index("lundi 12 octobre 2026 à 10 h 00") < rendu.index("Votre entretien") < rendu.index("Cordialement")
    assert "Rejoindre l'entretien en ligne" in rendu and 'href="https://meet.injara.site/x"' in rendu
    sur_site = mail_html.rendre(CORPS, mail_html.Signature(nom="Cabinet Ndong"), mail_html.Entretien("lundi 12 octobre 2026", "10 h 00", "1 heure", "Bonapriso"))
    assert "Bonapriso" in sur_site and "Rejoindre" not in sur_site


def test_mime_texte_et_version_mise_en_forme():
    message = construire_mime(MailSortant("awa@x.cm", "Invitation", "Bonjour,\n\nÀ bientôt.", html="<p>Bonjour,</p>"), "rh@cabinet.cm")
    lu = email.message_from_bytes(message.as_bytes(), policy=policy.default)
    assert lu.get_content_type() == "multipart/alternative"
    assert lu.get_body(("plain",)).get_content().strip() == "Bonjour,\n\nÀ bientôt."
    assert "<p>Bonjour,</p>" in lu.get_body(("html",)).get_content()
    seul = construire_mime(MailSortant("awa@x.cm", "Invitation", "Bonjour"))
    assert seul.get_content_type() == "text/plain"


def test_envoi_reel_porte_la_version_mise_en_forme(connecte, app):
    """Le mail envoyé au candidat contient l'en-tête de l'entreprise ; l'aperçu des modèles aussi."""
    connecte.put("/entreprise", json={"nom": "Cabinet Ndong", "ville": "Douala"})
    r = connecte.post("/parametres/mails/modeles/invitation/apercu", json={"objet": "Invitation {poste}", "corps": "Bonjour {civilite_nom},\n\nLe {date}.\n\n{entreprise}"})
    apercu = r.json()
    assert r.status_code == 200 and "Cabinet Ndong" in apercu["html"] and "Votre entretien" in apercu["html"]
    refus = connecte.post("/parametres/mails/modeles/refus/apercu", json={"objet": "x", "corps": "Bonjour {civilite_nom},"}).json()
    assert "Votre entretien" not in refus["html"] and "Douala" in refus["html"]
