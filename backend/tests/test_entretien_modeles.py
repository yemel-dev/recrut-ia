from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.models import AlerteTriche, Base, Candidature, Entretien


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _candidature(session) -> Candidature:
    c = Candidature(cle="mail-1", fichier_cv="cv.pdf", nom_fichier_cv="cv.pdf", sha256_cv="0" * 64)
    session.add(c)
    session.flush()
    return c


def test_valeurs_par_defaut(session):
    e = Entretien(candidature_id=_candidature(session).id, code_invitation="ABC123")
    session.add(e)
    session.commit()
    assert e.statut == "planifie"
    assert e.consentement_enregistrement is False
    assert e.score_entretien is None


def test_code_invitation_unique(session):
    c = _candidature(session)
    session.add_all([Entretien(candidature_id=c.id, code_invitation="X"), Entretien(candidature_id=c.id, code_invitation="X")])
    with pytest.raises(IntegrityError):
        session.commit()


def test_suppression_en_cascade(session):
    c = _candidature(session)
    e = Entretien(candidature_id=c.id, code_invitation="X")
    session.add(e)
    session.flush()
    session.add(AlerteTriche(entretien_id=e.id, type_alerte="perte_focus", details={"duree_s": 4}))
    session.commit()
    session.delete(c)
    session.commit()
    assert session.scalars(select(Entretien)).all() == []
    assert session.scalars(select(AlerteTriche)).all() == []
