"""Exporte les logos d'INJARA (design-ui-ux-graphic-chart/, PNG 4500 px) aux tailles utilisées par l'interface.

Le dessin n'est jamais retouché : recadrage sur la partie visible, marge uniforme, réduction (Lanczos).
Produit aussi l'icône de l'application (symbole vert sur carré arrondi bleu nuit), de 16 à 1024 px, et le .ico Windows.

Usage, depuis la racine du dépôt : .venv/bin/python desktop/scripts/exporter-logos.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

RACINE = Path(__file__).resolve().parents[2]
SOURCES = RACINE / "design-ui-ux-graphic-chart"
MARQUE = RACINE / "desktop" / "renderer" / "public" / "marque"
PACKAGING = RACINE / "desktop" / "packaging"
PUBLIC = RACINE / "desktop" / "renderer" / "public"

NUIT_900 = (3, 30, 64, 255)


def recadrer(nom: str, marge: float = 0.0) -> Image.Image:
    image = Image.open(SOURCES / nom).convert("RGBA")
    image = image.crop(image.getbbox())
    if marge:
        bord = round(max(image.size) * marge)
        fond = Image.new("RGBA", (image.width + 2 * bord, image.height + 2 * bord), (0, 0, 0, 0))
        fond.paste(image, (bord, bord))
        image = fond
    return image


def reduire(image: Image.Image, hauteur: int) -> Image.Image:
    largeur = round(image.width * hauteur / image.height)
    return image.resize((largeur, hauteur), Image.LANCZOS)


def exporter(image: Image.Image, nom: str, hauteurs) -> None:
    for h in hauteurs:
        reduire(image, h).save(MARQUE / f"{nom}-{h}.webp", "WEBP", quality=92, method=6)


def icone(taille: int, symbole: Image.Image) -> Image.Image:
    """Symbole vert centré sur un carré arrondi bleu nuit (proportions des icônes d'application)."""
    sur = 4  # sur-échantillonnage pour des bords lisses
    cote = taille * sur
    fond = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    ImageDraw.Draw(fond).rounded_rectangle((0, 0, cote - 1, cote - 1), radius=round(cote * 0.225), fill=NUIT_900)
    interieur = round(cote * (0.66 if taille >= 32 else 0.74))
    s = symbole.resize((interieur, interieur), Image.LANCZOS)
    fond.alpha_composite(s, ((cote - interieur) // 2, (cote - interieur) // 2))
    return fond.resize((taille, taille), Image.LANCZOS)


def main() -> None:
    MARQUE.mkdir(parents=True, exist_ok=True)

    symbole_vert = recadrer("23.png")
    exporter(symbole_vert, "symbole-vert", (48, 96, 192, 512))
    exporter(recadrer("26.png"), "symbole-blanc", (96, 512))
    exporter(recadrer("24.png"), "symbole-nuit", (96, 512))

    exporter(recadrer("27.png"), "logotype-nuit", (64, 128))  # « Injara » bleu nuit, point vert
    exporter(recadrer("28.png"), "logotype-blanc", (64, 128))
    exporter(recadrer("21.png"), "logo-vertical-couleur", (256, 512))  # symbole vert + logotype bleu nuit
    exporter(recadrer("32.png"), "logo-vertical-blanc", (256, 512))

    tailles = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
    icones = {t: icone(t, symbole_vert) for t in tailles}
    dossier_icones = PACKAGING / "icones"
    dossier_icones.mkdir(parents=True, exist_ok=True)
    for t, im in icones.items():
        im.save(dossier_icones / f"{t}x{t}.png")
    icones[1024].save(PACKAGING / "icon.png")
    icones[512].save(PUBLIC / "icon.png")
    icones[256].save(PACKAGING / "icon.ico", sizes=[(t, t) for t in (16, 24, 32, 48, 64, 128, 256)], append_images=[icones[t] for t in (16, 24, 32, 48, 64, 128)])
    print(f"Logos exportés dans {MARQUE.relative_to(RACINE)}, icônes dans {PACKAGING.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
