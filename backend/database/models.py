from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class OffreEmploi(Base):
    __tablename__ = "offres_emploi"
    id                  = Column(Integer, primary_key=True)
    titre               = Column(String(255), nullable=False)
    description         = Column(Text)
    competences_requises = Column(Text)  # JSON
    experience_min      = Column(Integer, default=0)
    formation_requise   = Column(String(50))
    is_active           = Column(Boolean, default=True)
    date_creation       = Column(DateTime, server_default=func.now())


class Candidat(Base):
    __tablename__ = "candidats"
    id             = Column(Integer, primary_key=True)
    nom            = Column(String(100))
    prenom         = Column(String(100))
    email          = Column(String(255), unique=True)
    cv_path        = Column(String(500))
    date_reception = Column(DateTime, server_default=func.now())


class AnalyseCV(Base):
    __tablename__ = "analyses_cv"
    id                  = Column(Integer, primary_key=True)
    candidat_id         = Column(Integer, nullable=False)
    offre_id            = Column(Integer, nullable=False)
    competences         = Column(Text)   # JSON
    experience_annees   = Column(Float, default=0.0)
    formation_niveau    = Column(String(50))
    score_competences   = Column(Float, default=0.0)
    score_experience    = Column(Float, default=0.0)
    score_formation     = Column(Float, default=0.0)
    score_adequation    = Column(Float, default=0.0)
    score_global        = Column(Float, default=0.0)
    score_potentiel     = Column(String(20))
    justification       = Column(Text)
    date_analyse        = Column(DateTime, server_default=func.now())


class Entretien(Base):
    __tablename__ = "entretiens"
    id                  = Column(Integer, primary_key=True)
    candidat_id         = Column(Integer, nullable=False)
    offre_id            = Column(Integer, nullable=False)
    code_invitation     = Column(String(20), unique=True)
    date_entretien      = Column(DateTime)
    statut              = Column(String(20), default="planifie")
    score_regard        = Column(Float)
    score_contenu       = Column(Float)
    score_confiance     = Column(Float)
    score_entretien     = Column(Float)
    transcription       = Column(Text)
    rapport_path        = Column(String(500))


class AlerteTriche(Base):
    __tablename__ = "alertes_triche"
    id            = Column(Integer, primary_key=True)
    entretien_id  = Column(Integer, nullable=False)
    type_alerte   = Column(String(100))
    details       = Column(Text)
    timestamp     = Column(DateTime, server_default=func.now())
