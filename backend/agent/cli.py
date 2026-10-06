"""Pilotage en ligne de commande, pratique pour tester vite.

    python -m backend.agent.cli sync
    python -m backend.agent.cli list
    python -m backend.agent.cli config                         (voir la règle de récupération)
    python -m backend.agent.cli config --sync-mode new_only    (seulement les nouveaux emails)
    python -m backend.agent.cli config --period-days 14        (emails des 14 derniers jours)
    python -m backend.agent.cli config --since-date 2026-10-01 (depuis une date)
    python -m backend.agent.cli config --sync-mode all         (tout l'historique)
    python -m backend.agent.cli config --unread-only           (--no-unread-only pour annuler)
    python -m backend.agent.cli config --profile prudent       (ou new_only, everything)
    python -m backend.agent.cli config --add-ignored-sender linkedin.com --max-mb 10 --types pdf
    python -m backend.agent.cli preview --period-days 30       (aperçu AVANT import, rien n'est enregistré)
    python -m backend.agent.cli ignored                        (liste des emails ignorés et pourquoi)
    python -m backend.agent.cli recover --id 3                 (importer quand même)
    python -m backend.agent.cli diagnose --days 7     (pourquoi un email n'est pas récupéré ?)
    python -m backend.agent.cli reset-cursor          (re-regarder toute la période)
    python -m backend.agent.cli import --path C:\\mes_cv      (dossier, fichier ou .zip)
    python -m backend.agent.cli watch --minutes 1
    python -m backend.agent.cli connect       (Gmail / Workspace, mode real)
    python -m backend.agent.cli connect-imap  (IMAP, mode real)

Ajouter --mode fake|real pour forcer le mode (sinon GMAIL_MODE du .env, "fake" par défaut).
"""
from __future__ import annotations

import argparse
import logging
import time

from .agent import create_agent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="injara-gmail")
    parser.add_argument("command", choices=["connect", "connect-imap", "sync", "list", "watch", "status", "import", "diagnose", "reset-cursor", "config", "preview", "ignored", "recover"])
    parser.add_argument("--mode", choices=["fake", "real"])
    parser.add_argument("--path", help="fichier ou dossier à importer (commande 'import')")
    parser.add_argument("--days", type=int, default=7, help="fenêtre de l'audit (commande 'diagnose')")
    parser.add_argument("--sync-mode", choices=["new_only", "last_days", "since_date", "all"], help="commande 'config'")
    parser.add_argument("--period-days", type=int, help="commande 'config' : nombre de jours (mode last_days)")
    parser.add_argument("--since-date", help="commande 'config' : date AAAA-MM-JJ (mode since_date)")
    parser.add_argument("--unread-only", action=argparse.BooleanOptionalAction, default=None, help="commande 'config' : emails non lus seulement")
    parser.add_argument("--profile", choices=["prudent", "new_only", "everything"], help="commande 'config' : appliquer un profil")
    parser.add_argument("--ignore-automatic", action=argparse.BooleanOptionalAction, default=None, help="ignorer les emails automatiques")
    parser.add_argument("--add-ignored-sender", action="append", metavar="ADRESSE_OU_DOMAINE", help="ignorer cet expéditeur/domaine (répétable)")
    parser.add_argument("--remove-ignored-sender", action="append", metavar="ADRESSE_OU_DOMAINE", help="ne plus ignorer (répétable)")
    parser.add_argument("--max-mb", type=int, help="taille maximale d'une pièce jointe, en Mo")
    parser.add_argument("--types", nargs="+", choices=["pdf", "docx"], help="types de fichiers acceptés")
    parser.add_argument("--folder", help="dossier (IMAP) ou étiquette (Gmail) à lire ; \"\" pour tout")
    parser.add_argument("--id", type=int, help="commande 'recover' : numéro dans la liste des ignorés")
    parser.add_argument("--minutes", type=float, default=None, help="intervalle pour 'watch'")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    agent = create_agent(mode=args.mode)

    # Bandeau : évite de croire qu'on lit une vraie boîte alors qu'on est en simulation
    from .settings import load_settings

    if agent.mode == "fake":
        print("!!! MODE SIMULATION (GMAIL_MODE=fake) : boîte mail FAUSSE avec 5 CV de démonstration, aucune vraie boîte n'est lue.")
        print("!!! Pour lire une vraie boîte : mettre GMAIL_MODE=real dans le fichier .env à la racine du projet (ou ajouter --mode real).")
    else:
        print(f"Mode RÉEL — compte : {agent.account_email or 'non connecté'} ({agent.provider or 'aucun'})")
    if load_settings().env_file is None:
        print("Info : aucun fichier .env trouvé à la racine du projet (les valeurs par défaut sont utilisées).")

    if args.command == "connect":
        agent.connect()
        print("Connecté.")
    elif args.command == "connect-imap":
        import getpass

        from .accounts import ImapConfig, detect_imap

        address = input("Adresse e-mail : ").strip()
        preset = detect_imap(address)
        host = preset.host if preset else input("Serveur IMAP (ex. imap.mail.ovh.net) : ").strip()
        agent.connect_imap(ImapConfig(address, host), getpass.getpass("Mot de passe d'application : "))
        print("Connecté.")
    elif args.command == "import":
        from pathlib import Path

        if not args.path:
            parser.error("import nécessite --path")
        target = Path(args.path)
        found = [f for f in (target.rglob("*") if target.is_dir() else [target]) if f.is_file()]
        result = agent.import_files([(f.name, f.read_bytes()) for f in found])
        print(f"{len(result.imported)} importé(s), {result.duplicates_skipped} doublon(s), {len(result.rejected)} rejeté(s)")
        for r in result.rejected:
            print(f"  ! {r.filename} : {r.reason}")
    elif args.command == "diagnose":
        from .diagnostics import format_report, run_audit

        print(format_report(run_audit(agent, days=args.days)))
    elif args.command in ("config", "preview"):
        from .schemas import SyncConfig

        try:
            changes: dict = {}
            if args.sync_mode:
                changes["mode"] = args.sync_mode
            if args.period_days is not None:
                changes["days"] = args.period_days
                changes.setdefault("mode", "last_days")  # --period-days seul suffit à choisir ce mode
            if args.since_date:
                changes["since_date"] = args.since_date
                changes.setdefault("mode", "since_date")
            if args.unread_only is not None:
                changes["unread_only"] = args.unread_only
            if args.ignore_automatic is not None:
                changes["ignore_automatic"] = args.ignore_automatic
            if args.max_mb is not None:
                changes["max_attachment_mb"] = args.max_mb
            if args.types:
                changes["allowed_extensions"] = args.types
            if args.folder is not None:
                changes["folder"] = args.folder
            base = SyncConfig(**{k: v for k, v in agent.sync_config._editable().items()})
            if args.profile:
                from .schemas import PROFILES

                base = PROFILES[args.profile].config.model_copy(deep=True)
            senders = list(base.ignored_senders)
            from .parsing import normalize_sender_rule

            for entry in args.add_ignored_sender or []:
                senders.append(entry)
            drop = {normalize_sender_rule(e) for e in (args.remove_ignored_sender or [])}
            changes["ignored_senders"] = [e for e in senders if normalize_sender_rule(e) not in drop]
            new = SyncConfig(**{**base._editable(), **changes})
        except ValueError as exc:
            errors = getattr(exc, "errors", None)
            parser.error(errors()[0]["msg"].replace("Value error, ", "") if errors else str(exc))
        if args.command == "config":
            if new._editable() != agent.sync_config._editable():
                agent.update_config(new)
                print("Configuration enregistrée.")
            print(f"Profil : {agent.sync_config.profile}")
            print(agent.sync_config.description)
            for note in agent.sync_config.warnings:
                print(f"  ATTENTION : {note}")
        else:  # preview : évalue ces réglages SANS les enregistrer ni rien télécharger
            report = agent.preview(new)
            print(report.description)
            print(f"{report.emails_with_cv} email(s) avec CV : {report.to_import} à importer, {report.already_imported} déjà importé(s), {report.ignored} ignoré(s)"
                  + (" (liste tronquée : il y en a plus)" if report.truncated else ""))
            for item in report.samples:
                tag = {"to_import": "IMPORTER ", "already_imported": "DÉJÀ PRIS", "ignored": "IGNORÉ   "}[item.outcome]
                print(f"  [{tag}] {item.received_at:%d/%m %H:%M}  {item.sender_email:<30} {item.filename}" + (f"  -> {item.reason}" if item.reason else ""))
            print("Rien n'a été téléchargé ni enregistré.")
    elif args.command == "ignored":
        items = agent.ledger.list_ignored(200)
        print(f"{len(items)} pièce(s) jointe(s) ignorée(s) :" if items else "Aucun email ignoré.")
        for item in items:
            print(f"  #{item.id:<4} {item.received_at:%d/%m %H:%M}  {item.sender_email:<30} {item.filename}\n         -> {item.reason}")
        if items:
            print("Pour importer l'un d'eux malgré tout : python -m backend.agent.cli recover --id NUMERO")
    elif args.command == "recover":
        if args.id is None:
            parser.error("recover nécessite --id")
        try:
            print(agent.recover_ignored(args.id).detail)
        except KeyError:
            print("Numéro introuvable (voir la commande 'ignored').")
    elif args.command == "reset-cursor":
        agent.ledger.delete_state(agent._cursor_key)
        agent.ledger.delete_state(agent._baseline_key)
        print("Curseur remis à zéro : la prochaine synchro repart de la règle de récupération (voir la commande 'config').")
    elif args.command == "status":
        print(agent.status().model_dump_json(indent=2))
    elif args.command == "sync":
        print(agent.sync_config.describe())
        result = agent.sync_once()
        print(f"Emails regardés depuis : {result.since.astimezone():%d/%m/%Y %H:%M}" if result.since else "Emails regardés depuis : le début de la boîte")
        print(f"{len(result.new_cvs)} nouveau(x) CV, {result.duplicates_skipped} doublon(s), {len(result.errors)} erreur(s)")
        for cv in result.new_cvs:
            print(f"  - {cv.sender_name} <{cv.sender_email}> : {cv.saved_path}")
        for item in result.skipped:
            print(f"  ~ écarté : {item.filename} ({item.sender_email}) — {item.reason}")
        for error in result.errors:
            print(f"  ! erreur : {error}")
        if result.ignored_count:
            print(f"  {result.ignored_count} pièce(s) jointe(s) ignorée(s) par vos règles (voir : python -m backend.agent.cli ignored)")
        if result.truncated:
            print("  ... Limite par synchronisation atteinte : relancez « sync » pour traiter la suite (ou augmentez GMAIL_MAX_RESULTS).")
    elif args.command == "list":
        for cv in agent.ledger.list_cvs(100):
            print(f"{cv.received_at:%Y-%m-%d %H:%M}  {cv.sender_name:<25} {cv.filename}")
    elif args.command == "watch":
        agent.subscribe(lambda e: print(f"[{e.type}] {e.message}"))
        agent.start_watching(args.minutes)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            agent.stop_watching()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
