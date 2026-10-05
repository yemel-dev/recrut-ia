"""Audit : « pourquoi tel email / tel CV n'est pas récupéré ? »

Lit la boîte mail comme le ferait l'agent (sans rien télécharger de définitif,
sans rien enregistrer) et explique, email par email, ce qui se passerait à la
prochaine synchronisation. Utilisable en ligne de commande ou via l'API.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .client import SUPPORTED_EXTENSIONS, RawAttachment, RawMessage
from .errors import NotConnectedError
from .importer import looks_valid

if TYPE_CHECKING:
    from .agent import GmailAgent


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def _classify(agent: "GmailAgent", message: RawMessage, attachment: RawAttachment) -> dict[str, str]:
    """Même logique que la vraie synchronisation, mais sans rien écrire."""
    name = attachment.filename
    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        return {"filename": name, "verdict": "ignoré", "reason": "format non pris en charge (PDF ou DOCX uniquement)"}
    status = agent.ledger.seen_status(message.id, attachment.attachment_id)
    if status == "saved":
        return {"filename": name, "verdict": "déjà récupéré", "reason": "ce CV est déjà dans la base"}
    if status == "duplicate":
        return {"filename": name, "verdict": "doublon", "reason": "déjà écarté lors d'une synchronisation : même contenu qu'un CV existant"}
    if status == "invalid":
        return {"filename": name, "verdict": "rejeté", "reason": "déjà écarté : fichier invalide"}
    data = agent.client.download_attachment(message.id, attachment.attachment_id)  # type: ignore[union-attr]
    if not looks_valid(Path(name).suffix.lower(), data):
        return {"filename": name, "verdict": "rejeté", "reason": "fichier invalide (ce n'est pas un vrai PDF/DOCX)"}
    known = agent.ledger.cv_by_sha(hashlib.sha256(data).hexdigest())
    if known is not None:
        return {
            "filename": name,
            "verdict": "doublon",
            "reason": f"même contenu que « {known.filename} » déjà enregistré le {known.received_at:%d/%m/%Y %H:%M} "
            "(un CV renvoyé tel quel n'est pas recompté)",
        }
    return {"filename": name, "verdict": "NOUVEAU", "reason": "sera récupéré à la prochaine synchronisation"}


def run_audit(agent: "GmailAgent", days: int = 7, limit: int = 30) -> dict[str, Any]:
    if agent.client is None:
        raise NotConnectedError("Gmail / IMAP n'est pas connecté")
    client: Any = agent.client
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    last = agent.ledger.get_state(agent._cursor_key)
    sync_since = agent.window_start(now)  # None = tout l'historique

    with agent._sync_lock:  # on évite de croiser une synchronisation en cours
        saved_filter = getattr(client, "skip_filter", None)
        if hasattr(client, "skip_filter"):
            client.skip_filter = None  # on veut voir la réalité, pas les emails déjà « marqués vus »
        if hasattr(client, "_no_cv"):
            client._no_cv.clear()
        try:
            detected = {m.id: m for m in client.list_cv_messages(since, agent.max_results)}
            mailbox = client.audit_recent(since, limit) if hasattr(client, "audit_recent") else {"messages": []}
            entries = []
            for raw in sorted(mailbox["messages"], key=lambda m: m["received_at"] or now, reverse=True):
                entry: dict[str, Any] = {
                    "received_at": _iso(raw["received_at"]),
                    "sender": raw["sender"],
                    "subject": raw["subject"],
                    "attachments": raw["attachments"],
                    "labels": raw.get("labels"),
                }
                message = detected.get(raw["id"])
                if message is not None:
                    entry["seen_by_agent"] = True
                    entry["results"] = [_classify(agent, message, a) for a in message.attachments]
                    if sync_since and raw["received_at"] and raw["received_at"] < sync_since:
                        entry["note"] = "plus ancien que la fenêtre de la prochaine synchro (traité seulement via 'reset-cursor')"
                else:
                    entry["seen_by_agent"] = False
                    if not raw["attachments"]:
                        entry["reason"] = "aucune pièce jointe"
                    else:
                        entry["reason"] = "pièces jointes non reconnues comme CV (PDF/DOCX attendus) : " + ", ".join(raw["attachments"])
                entries.append(entry)
        finally:
            if hasattr(client, "skip_filter"):
                client.skip_filter = saved_filter

    messages_with_cv = [e for e in entries if e["seen_by_agent"]]
    verdicts = [r["verdict"] for e in messages_with_cv for r in e["results"]]
    newest = max((m["received_at"] for m in mailbox["messages"] if m["received_at"]), default=None)
    return {
        "account": {"mode": agent.mode, "provider": agent.provider, "email": agent.account_email},
        "sync_rule": agent.sync_config.describe(),
        "window": {
            "audited_days": days,
            "audited_since": _iso(since),
            "last_sync_at": last,
            "next_sync_looks_since": _iso(sync_since),
        },
        "mailbox": {
            "folder": mailbox.get("folder"),
            "folders_on_server": mailbox.get("folders", []),
            "total_in_folder": mailbox.get("total_in_folder"),
            "emails_in_window": len(mailbox["messages"]),
            "newest_email_at": _iso(newest),
        },
        "database": {
            "total_cvs": agent.ledger.count_cvs(),
            "latest_cvs": [
                {"filename": c.filename, "received_at": _iso(c.received_at), "source": c.source}
                for c in agent.ledger.list_cvs(3)
            ],
        },
        "summary": {
            "emails_seen": len(entries),
            "emails_with_a_cv": len(messages_with_cv),
            "to_be_collected": verdicts.count("NOUVEAU"),
            "duplicates": verdicts.count("doublon"),
            "already_collected": verdicts.count("déjà récupéré"),
            "rejected": verdicts.count("rejeté"),
        },
        "emails": entries,
    }


def format_report(report: dict[str, Any]) -> str:
    """Rapport lisible pour la ligne de commande."""
    a, w, m, d, s = report["account"], report["window"], report["mailbox"], report["database"], report["summary"]
    lines = [
        "=== AUDIT DU MODULE 1 ===",
        f"Compte : {a['email'] or '?'} ({a['provider']}, mode {a['mode']})",
        f"Règle de récupération : {report['sync_rule']}",
        f"Dossier lu : {m['folder']} — {m['total_in_folder']} email(s) au total dans ce dossier",
    ]
    if m["folders_on_server"]:
        lines.append(f"Dossiers du serveur : {', '.join(m['folders_on_server'])}")
    lines += [
        f"Dernier email visible dans la fenêtre : {m['newest_email_at'] or 'AUCUN'}",
        f"Dernière synchronisation : {w['last_sync_at'] or 'jamais'} → la prochaine regarde depuis {w['next_sync_looks_since'] or 'le début de la boîte'}",
        f"Base : {d['total_cvs']} CV (derniers : {', '.join(c['filename'] for c in d['latest_cvs']) or 'aucun'})",
        "",
        f"Emails examinés ({w['audited_days']} derniers jours) : {s['emails_seen']} — avec CV détecté : {s['emails_with_a_cv']}",
        f"  → à récupérer : {s['to_be_collected']} | déjà récupérés : {s['already_collected']} | doublons : {s['duplicates']} | rejetés : {s['rejected']}",
        "",
    ]
    for e in report["emails"]:
        when = (e["received_at"] or "date inconnue")[:16].replace("T", " ")
        lines.append(f"[{when}] {e['sender']} — « {e['subject']} »")
        if e["seen_by_agent"]:
            for r in e["results"]:
                lines.append(f"     {r['verdict'].upper():<14} {r['filename']} : {r['reason']}")
            if e.get("note"):
                lines.append(f"     ({e['note']})")
        else:
            lines.append(f"     IGNORÉ : {e['reason']}")
        if e.get("labels"):
            lines.append(f"     étiquettes Gmail : {', '.join(e['labels'])}")
    if not report["emails"]:
        lines.append("Aucun email dans la fenêtre : vérifiez que c'est le bon compte/dossier, ou augmentez --days.")
    return "\n".join(lines)
