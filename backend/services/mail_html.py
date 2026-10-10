"""Version mise en forme (HTML) des mails aux candidats, envoyée avec la version texte.

Le texte vient du modèle rempli (modeles_mail.remplir) : ses paragraphes sont repris tels quels, échappés, avec les
liens rendus cliquables. Autour : un en-tête au nom de l'entreprise, et pour une invitation un encadré « Votre
entretien » (date, heure, durée, lieu) avec un bouton pour rejoindre la visio. Le pied de page reprend les
coordonnées de l'entreprise (profil entreprise).

HTML de mail : tableaux et styles en ligne uniquement (Gmail, Outlook et les messageries mobiles ignorent les
feuilles de style), largeur 600 px, polices système. Aucune image ni ressource externe : rien à télécharger, rien
qui puisse pister l'ouverture du mail.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

NUIT = "#031e40"
VERT = "#00bf63"
VERT_FONCE = "#007a3f"
FOND = "#f2f5f9"
TEXTE = "#1f2a37"
DOUX = "#5b6878"
TRAIT = "#e3e8ef"
POLICE = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

_LIEN = re.compile(r"https?://[^\s<>\"']+[^\s<>\"'.,;:!?)]")


@dataclass
class Entretien:
    """Ce que l'encadré « Votre entretien » affiche (valeurs déjà formatées pour le candidat)."""

    date: str
    heure: str
    duree: str
    lieu: str  # adresse, ou « En ligne (visioconférence) »
    lien: str | None = None  # lien de la visio : bouton « Rejoindre l'entretien »
    titre: str = "Votre entretien"


@dataclass
class Signature:
    """Coordonnées de l'entreprise pour l'en-tête et le pied de page."""

    nom: str
    ville: str | None = None
    email: str | None = None
    telephone: str | None = None
    secteur: str | None = None
    lignes: list[str] = field(default_factory=list)

    @classmethod
    def depuis_profil(cls, profil: dict | None) -> Signature:
        profil = profil or {}
        return cls(
            nom=(profil.get("nom") or "").strip() or "Votre entreprise",
            ville=(profil.get("ville") or "").strip() or None,
            email=(profil.get("email_pro") or "").strip() or None,
            telephone=(profil.get("telephone") or "").strip() or None,
            secteur=(profil.get("secteur") or "").strip() or None,
        )


def rendre(corps: str, signature: Signature, entretien: Entretien | None = None, objet: str = "") -> str:
    """Le mail complet en HTML. L'encadré de l'entretien se place après le paragraphe qui annonce la date."""
    paragraphes = [p.strip("\n") for p in re.split(r"\n\s*\n", corps or "") if p.strip()]
    blocs = []
    encadre_place = entretien is None
    for i, paragraphe in enumerate(paragraphes):
        blocs.append(_paragraphe(paragraphe, premier=i == 0))
        if not encadre_place and entretien and (entretien.date in paragraphe or i == len(paragraphes) - 1):
            blocs.append(_encadre(entretien))
            encadre_place = True
    if not encadre_place and entretien:
        blocs.insert(1 if blocs else 0, _encadre(entretien))
    return _gabarit("".join(blocs), signature, objet)


# --- Morceaux ----------------------------------------------------------------------------------------------------


def _texte(texte: str) -> str:
    """Échappe le texte, rend les liens cliquables et garde les retours à la ligne."""
    morceaux, position = [], 0
    for lien in _LIEN.finditer(texte):
        morceaux.append(html.escape(texte[position:lien.start()]))
        url = html.escape(lien.group(0), quote=True)
        morceaux.append(f'<a href="{url}" style="color:{VERT_FONCE};text-decoration:underline;word-break:break-all;">{url}</a>')
        position = lien.end()
    morceaux.append(html.escape(texte[position:]))
    return "".join(morceaux).replace("\n", "<br>")


def _paragraphe(texte: str, premier: bool = False) -> str:
    style = f"margin:0 0 18px 0;font-family:{POLICE};font-size:16px;line-height:1.65;color:{TEXTE};"
    if premier:
        style += f"font-weight:600;color:{NUIT};"
    return f'<p style="{style}">{_texte(texte)}</p>'


def _encadre(e: Entretien) -> str:
    lignes = "".join(
        f"""<tr>
          <td style="padding:7px 0;font-family:{POLICE};font-size:13px;color:{DOUX};width:90px;vertical-align:top;">{libelle}</td>
          <td style="padding:7px 0;font-family:{POLICE};font-size:15px;color:{NUIT};font-weight:600;">{_texte(valeur)}</td>
        </tr>"""
        for libelle, valeur in (("Date", e.date), ("Heure", e.heure), ("Durée", e.duree), ("Lieu", e.lieu))
        if valeur
    )
    bouton = ""
    if e.lien:
        url = html.escape(e.lien, quote=True)
        bouton = f"""<tr><td colspan="2" style="padding:14px 0 2px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
            <td style="border-radius:8px;background:{NUIT};">
              <a href="{url}" style="display:inline-block;padding:12px 22px;font-family:{POLICE};font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;border-radius:8px;">Rejoindre l'entretien en ligne</a>
            </td>
          </tr></table>
          <p style="margin:10px 0 0 0;font-family:{POLICE};font-size:12px;line-height:1.5;color:{DOUX};">Le lien s'ouvre dans votre navigateur : rien à installer.</p>
        </td></tr>"""
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 22px 0;">
      <tr><td style="background:#f3fbf6;border:1px solid #cdeedb;border-left:4px solid {VERT};border-radius:10px;padding:16px 20px;">
        <p style="margin:0 0 6px 0;font-family:{POLICE};font-size:12px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:{VERT_FONCE};">{html.escape(e.titre)}</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{lignes}{bouton}</table>
      </td></tr>
    </table>"""


def _gabarit(contenu: str, s: Signature, objet: str) -> str:
    initiale = html.escape((s.nom[:1] or "?").upper())
    nom = html.escape(s.nom)
    sous_titre = html.escape(s.secteur) if s.secteur else "Recrutement"
    coordonnees = " · ".join(html.escape(x) for x in (s.ville, s.email, s.telephone) if x)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{html.escape(objet)}</title>
</head>
<body style="margin:0;padding:0;background:{FOND};">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(objet)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{FOND};">
  <tr><td align="center" style="padding:28px 12px;">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid {TRAIT};">
      <tr><td style="background:{NUIT};padding:22px 32px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="width:42px;height:42px;border-radius:21px;background:{VERT};text-align:center;vertical-align:middle;font-family:{POLICE};font-size:19px;font-weight:700;color:{NUIT};">{initiale}</td>
          <td style="padding-left:14px;">
            <p style="margin:0;font-family:{POLICE};font-size:18px;font-weight:700;color:#ffffff;">{nom}</p>
            <p style="margin:2px 0 0 0;font-family:{POLICE};font-size:13px;color:#8fe3b8;">{sous_titre}</p>
          </td>
        </tr></table>
      </td></tr>
      <tr><td style="height:4px;background:{VERT};font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr><td style="padding:34px 32px 16px 32px;">{contenu}</td></tr>
      <tr><td style="padding:18px 32px 26px 32px;border-top:1px solid {TRAIT};">
        <p style="margin:0;font-family:{POLICE};font-size:13px;font-weight:600;color:{NUIT};">{nom}</p>
        {f'<p style="margin:4px 0 0 0;font-family:{POLICE};font-size:12px;color:{DOUX};">{coordonnees}</p>' if coordonnees else ''}
        <p style="margin:12px 0 0 0;font-family:{POLICE};font-size:11px;line-height:1.5;color:#8a96a6;">Vous recevez ce message suite à votre candidature. Pour toute question, répondez simplement à ce mail.</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""
