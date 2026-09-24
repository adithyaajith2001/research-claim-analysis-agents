# """
# db_schema.py

# WHAT: SQLAlchemy ORM models for every entity in the ER diagram (Fig 3) from
# your System Design submission: Researcher, Query, Paper, Claim, Evidence,
# Contradictions, Report, Agent.

# WHY REBUILT FROM SCRATCH: the old schema only had Paper + Claim, with evidence
# text stuffed into a column on Claim. That doesn't match the ERD you already
# submitted to your guide (which has Evidence as its own entity with a
# Reliability_Score, and Claim with its own Confidence_Score). If the code
# doesn't match the diagram, that's an easy, avoidable point of criticism.

# HOW: built against SQLite for local/laptop development (zero setup, single
# file on disk). Every line of SQLAlchemy model code here is IDENTICAL for
# PostgreSQL - only DATABASE_URL changes. This is intentional: you get to build
# and test today on your laptop, and swapping to real Postgres later (per your
# Non-Functional Requirements) is a one-line change, not a rewrite.

# WHEN this file is used: imported by claim_extraction_agent.py and
# evidence_strength_agent.py to write their outputs; imported by the frontend
# visualization script to read contradiction data back out.
# """

# from sqlalchemy import (
#     create_engine, Column, Integer, String, Float, Text, ForeignKey, DateTime
# )
# from sqlalchemy.orm import declarative_base, relationship, sessionmaker
# import datetime

# # --- Connection ---------------------------------------------------------
# # LOCAL (today, laptop): SQLite file.
# # LATER (deployment, per your NFRs): swap this one line for e.g.
# #   "postgresql://user:password@host:5432/claims_audit"
# # Nothing else in this file changes.
# DATABASE_URL = "sqlite:///claims_audit.db"

# Base = declarative_base()


# class Researcher(Base):
#     """ERD: Researcher (R_ID, Name, Email, Institution). Submits Queries (1:N)."""
#     __tablename__ = "researchers"
#     id = Column(Integer, primary_key=True, autoincrement=True)  # R_ID
#     name = Column(String, nullable=False)
#     email = Column(String)
#     institution = Column(String)
#     queries = relationship("Query", back_populates="researcher")


# class Query(Base):
#     """ERD: Query (Q_ID, Query-text, Timestamp). Retrieves Papers (1:N)."""
#     __tablename__ = "queries"
#     id = Column(Integer, primary_key=True, autoincrement=True)  # Q_ID
#     researcher_id = Column(Integer, ForeignKey("researchers.id"), nullable=True)
#     query_text = Column(Text, nullable=False)
#     timestamp = Column(DateTime, default=datetime.datetime.utcnow)
#     researcher = relationship("Researcher", back_populates="queries")
#     papers = relationship("Paper", back_populates="query")


# class Paper(Base):
#     """ERD: Paper (P_ID, Title, Author, Year, Source). Contains Claims (1:N)."""
#     __tablename__ = "papers"
#     id = Column(String, primary_key=True)  # P_ID - using arXiv id as natural key
#     query_id = Column(Integer, ForeignKey("queries.id"), nullable=True)
#     title = Column(String, nullable=False)
#     authors = Column(String)  # "Author" in ERD - comma-joined string of authors
#     year = Column(Integer)
#     source = Column(String)  # e.g. "arXiv", "Semantic Scholar"
#     source_url = Column(String)
#     query = relationship("Query", back_populates="papers")
#     claims = relationship("Claim", back_populates="paper")


# class Claim(Base):
#     """ERD: Claim (C_ID, Claim-Text, evidence_strength_score). Contained in Paper (1:N),
#     Supported_By Evidence, Conflicts (M:N via Contradictions)."""
#     __tablename__ = "claims"
#     id = Column(Integer, primary_key=True, autoincrement=True)  # C_ID
#     paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
#     claim_text = Column(Text, nullable=False)
#     claim_type = Column(String)  # hypothesis / finding / performance_claim / conclusion
#     section = Column(String)  # where in the paper this came from
#     benchmark_name = Column(String, nullable=True)  # domain-specific: e.g. "MMLU"
#     reported_value = Column(Float, nullable=True)  # domain-specific: e.g. 86.4 (%)
#     # WHAT: what KIND of number reported_value is - "absolute_accuracy" /
#     # "absolute_improvement" / "relative_improvement". WHY this exists:
#     # contradiction_agent.py originally compared reported_value across ANY
#     # two claims sharing a benchmark_name, which meant a standalone accuracy
#     # score (e.g. 95.22%) was being numerically diffed against improvement
#     # deltas (e.g. 1.3%) as if they were the same measurement - they are not.
#     # Added so contradiction detection can group by (benchmark_name,
#     # value_type) and only compare genuinely like-for-like numbers.
#     value_type = Column(String, nullable=True)
#     evidence_strength_score = Column(Float, nullable=True)  # ERD: Evidence Strength Score
#     paper = relationship("Paper", back_populates="claims")
#     evidence = relationship("Evidence", back_populates="claim")


# class Evidence(Base):
#     """ERD: Evidence (E_ID, Citation_Text, Reliability_Score). Supported_By <-> Claim."""
#     __tablename__ = "evidence"
#     id = Column(Integer, primary_key=True, autoincrement=True)  # E_ID
#     claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
#     citation_text = Column(Text, nullable=False)  # exact supporting sentence(s)
#     reliability_score = Column(Float, nullable=True)  # filled by verification step
#     claim = relationship("Claim", back_populates="evidence")


# class Contradiction(Base):
#     """ERD: Contradictions (X_ID, Type, Severity), M:N between Claims.
#     NOTE: this table is Adithya's Contradiction Detection Agent's OUTPUT target.
#     It's included here (not built by us) so our DB schema and Adithya's agent
#     integrate cleanly - and so we can build/test our visualization component
#     against real schema shape instead of guessing."""
#     __tablename__ = "contradictions"
#     id = Column(Integer, primary_key=True, autoincrement=True)  # X_ID
#     claim_a_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
#     claim_b_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
#     relation_type = Column(String, nullable=False)  # "Agrees" / "Contradicts" / "Unrelated"
#     severity = Column(String, nullable=True)  # e.g. "Low" / "Medium" / "High"


# class Report(Base):
#     """ERD: Report (Report_ID, Generated_Date, Health_Score). Includes Contradictions."""
#     __tablename__ = "reports"
#     id = Column(Integer, primary_key=True, autoincrement=True)  # Report_ID
#     generated_date = Column(DateTime, default=datetime.datetime.utcnow)
#     health_score = Column(Float, nullable=True)  # aggregate literature-health metric


# def get_session(db_url: str = DATABASE_URL):
#     """WHAT: opens (and creates if needed) the database, returns a session.
#     WHEN: call this once at the start of any script that reads/writes the DB."""
#     engine = create_engine(db_url)
#     Base.metadata.create_all(engine)
#     Session = sessionmaker(bind=engine)
#     return Session()


# # ---------------------------------------------------------------------------
# # CRUD helpers
# # WHY these exist as functions (not inline session.add() calls scattered
# # everywhere): so extraction/scoring agents don't need to know SQLAlchemy
# # internals - they just call insert_claim_with_evidence(...) and it's done
# # consistently every time, with the paper->claim->evidence chain always
# # built correctly (claim first, flush to get its id, then evidence).
# # ---------------------------------------------------------------------------

# def upsert_paper(session, paper: dict, query_id: int = None):
#     """WHAT: insert or update a paper row.
#     WHEN: called once per paper before its claims are inserted."""
#     p = session.merge(Paper(
#         id=paper["id"],
#         query_id=query_id,
#         title=paper["title"],
#         authors=paper.get("authors", ""),
#         year=paper.get("year"),
#         source=paper.get("source", "arXiv"),
#         source_url=paper.get("source_url", f"https://arxiv.org/abs/{paper['id']}"),
#     ))
#     session.commit()
#     return p


# def insert_claim_with_evidence(session, claim_dict: dict) -> Claim:
#     """WHAT: inserts one Claim row + its linked Evidence row together.
#     WHY together: a claim without evidence is unverifiable and shouldn't
#     exist alone in this schema (matches your workflow diagram - unverified
#     claims get flagged, not silently dropped).
#     Expects claim_dict keys: paper_id, claim, section, claim_type,
#     source_sentence, benchmark_name (optional), reported_value (optional)."""
#     claim_row = Claim(
#         paper_id=claim_dict["paper_id"],
#         claim_text=claim_dict["claim"],
#         claim_type=claim_dict.get("claim_type"),
#         section=claim_dict.get("section"),
#         benchmark_name=claim_dict.get("benchmark_name"),
#         reported_value=claim_dict.get("reported_value"),
#         value_type=claim_dict.get("value_type"),
#     )
#     session.add(claim_row)
#     session.flush()  # populates claim_row.id without a full commit

#     session.add(Evidence(
#         claim_id=claim_row.id,
#         citation_text=claim_dict.get("source_sentence", ""),
#     ))
#     session.commit()
#     return claim_row


# def update_claim_score(session, claim_id: int, evidence_strength_score: float):
#     """WHAT: writes the Evidence Strength Agent's output back onto a claim."""
#     claim_row = session.get(Claim, claim_id)
#     claim_row.evidence_strength_score = evidence_strength_score
#     session.commit()


# def get_all_claims_for_paper(session, paper_id: str):
#     return session.query(Claim).filter(Claim.paper_id == paper_id).all()


# def contradiction_exists(session, claim_a_id: int, claim_b_id: int) -> bool:
#     """WHAT: checks whether this claim pair is already stored, in EITHER
#     order (a,b) or (b,a).
#     WHY: contradiction_agent.py can be rerun any time claims change; without
#     this check, every rerun would duplicate every pair already found."""
#     return session.query(Contradiction).filter(
#         ((Contradiction.claim_a_id == claim_a_id) & (Contradiction.claim_b_id == claim_b_id)) |
#         ((Contradiction.claim_a_id == claim_b_id) & (Contradiction.claim_b_id == claim_a_id))
#     ).first() is not None


# def insert_contradiction(session, claim_a_id: int, claim_b_id: int,
#                           relation_type: str, severity: str = None):
#     """WHAT: inserts one Contradiction row, unless this pair already exists.
#     WHEN: called by contradiction_agent.py once per compared claim pair.
#     Returns the new Contradiction row, or None if it was already stored
#     (skip, don't duplicate)."""
#     if contradiction_exists(session, claim_a_id, claim_b_id):
#         return None
#     row = Contradiction(
#         claim_a_id=claim_a_id,
#         claim_b_id=claim_b_id,
#         relation_type=relation_type,
#         severity=severity,
#     )
#     session.add(row)
#     session.commit()
#     return row

# def get_all_contradictions(session):
#     return session.query(Contradiction).all()

"""
db_schema.py

WHAT: SQLAlchemy ORM models for every entity in the ER diagram (Fig 3) from
your System Design submission: Researcher, Query, Paper, Claim, Evidence,
Contradictions, Report, Agent.

WHY REBUILT FROM SCRATCH: the old schema only had Paper + Claim, with evidence
text stuffed into a column on Claim. That doesn't match the ERD you already
submitted to your guide (which has Evidence as its own entity with a
Reliability_Score, and Claim with its own Confidence_Score). If the code
doesn't match the diagram, that's an easy, avoidable point of criticism.

HOW: built against SQLite for local/laptop development (zero setup, single
file on disk). Every line of SQLAlchemy model code here is IDENTICAL for
PostgreSQL - only DATABASE_URL changes. This is intentional: you get to build
and test today on your laptop, and swapping to real Postgres later (per your
Non-Functional Requirements) is a one-line change, not a rewrite.

WHEN this file is used: imported by claim_extraction_agent.py and
evidence_strength_agent.py to write their outputs; imported by the frontend
visualization script to read contradiction data back out.
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, ForeignKey, DateTime
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import datetime

# --- Connection ---------------------------------------------------------
# LOCAL (today, laptop): SQLite file.
# LATER (deployment, per your NFRs): swap this one line for e.g.
#   "postgresql://user:password@host:5432/claims_audit"
# Nothing else in this file changes.
DATABASE_URL = "sqlite:///claims_audit.db"

Base = declarative_base()


class Researcher(Base):
    """ERD: Researcher (R_ID, Name, Email, Institution). Submits Queries (1:N)."""
    __tablename__ = "researchers"
    id = Column(Integer, primary_key=True, autoincrement=True)  # R_ID
    name = Column(String, nullable=False)
    email = Column(String)
    institution = Column(String)
    queries = relationship("Query", back_populates="researcher")


class Query(Base):
    """ERD: Query (Q_ID, Query-text, Timestamp). Retrieves Papers (1:N)."""
    __tablename__ = "queries"
    id = Column(Integer, primary_key=True, autoincrement=True)  # Q_ID
    researcher_id = Column(Integer, ForeignKey("researchers.id"), nullable=True)
    query_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    researcher = relationship("Researcher", back_populates="queries")
    papers = relationship("Paper", back_populates="query")


class Paper(Base):
    """ERD: Paper (P_ID, Title, Author, Year, Source). Contains Claims (1:N)."""
    __tablename__ = "papers"
    id = Column(String, primary_key=True)  # P_ID - using arXiv id as natural key
    query_id = Column(Integer, ForeignKey("queries.id"), nullable=True)
    title = Column(String, nullable=False)
    authors = Column(String)  # "Author" in ERD - comma-joined string of authors
    year = Column(Integer)
    source = Column(String)  # e.g. "arXiv", "Semantic Scholar"
    source_url = Column(String)
    query = relationship("Query", back_populates="papers")
    claims = relationship("Claim", back_populates="paper")


class Claim(Base):
    """ERD: Claim (C_ID, Claim-Text, evidence_strength_score). Contained in Paper (1:N),
    Supported_By Evidence, Conflicts (M:N via Contradictions)."""
    __tablename__ = "claims"
    id = Column(Integer, primary_key=True, autoincrement=True)  # C_ID
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String)  # hypothesis / finding / performance_claim / conclusion
    section = Column(String)  # where in the paper this came from
    benchmark_name = Column(String, nullable=True)  # domain-specific: e.g. "MMLU"
    reported_value = Column(Float, nullable=True)  # domain-specific: e.g. 86.4 (%)
    # WHAT: what KIND of number reported_value is - "absolute_accuracy" /
    # "absolute_improvement" / "relative_improvement". WHY this exists:
    # contradiction_agent.py originally compared reported_value across ANY
    # two claims sharing a benchmark_name, which meant a standalone accuracy
    # score (e.g. 95.22%) was being numerically diffed against improvement
    # deltas (e.g. 1.3%) as if they were the same measurement - they are not.
    # Added so contradiction detection can group by (benchmark_name,
    # value_type) and only compare genuinely like-for-like numbers.
    value_type = Column(String, nullable=True)
    # WHAT: evaluation shot-setting ("0-shot", "5-shot", "few-shot") and
    # normalized metric name ("accuracy", "f1", ...) when the extraction
    # agent could establish them explicitly from the source text. WHY these
    # exist: contradiction_agent.py must not compare a 0-shot MMLU score
    # against a 5-shot MMLU score as if they measured the same thing - that
    # is a different evaluation condition, not a disagreement. Both fields
    # are nullable because not every claim's source text states them.
    evaluation_setting = Column(String, nullable=True)
    metric = Column(String, nullable=True)
    evidence_strength_score = Column(Float, nullable=True)  # ERD: Evidence Strength Score
    paper = relationship("Paper", back_populates="claims")
    evidence = relationship("Evidence", back_populates="claim")


class Evidence(Base):
    """ERD: Evidence (E_ID, Citation_Text, Reliability_Score). Supported_By <-> Claim."""
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True, autoincrement=True)  # E_ID
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    citation_text = Column(Text, nullable=False)  # exact supporting sentence(s)
    reliability_score = Column(Float, nullable=True)  # filled by verification step
    claim = relationship("Claim", back_populates="evidence")


class Contradiction(Base):
    """ERD: Contradictions (X_ID, Type, Severity), M:N between Claims.
    NOTE: this table is Adithya's Contradiction Detection Agent's OUTPUT target.
    It's included here (not built by us) so our DB schema and Adithya's agent
    integrate cleanly - and so we can build/test our visualization component
    against real schema shape instead of guessing."""
    __tablename__ = "contradictions"
    id = Column(Integer, primary_key=True, autoincrement=True)  # X_ID
    claim_a_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    claim_b_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    relation_type = Column(String, nullable=False)  # "Agrees" / "Contradicts" / "Unrelated"
    severity = Column(String, nullable=True)  # e.g. "Low" / "Medium" / "High"


class Report(Base):
    """ERD: Report (Report_ID, Generated_Date, Health_Score). Includes Contradictions."""
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)  # Report_ID
    generated_date = Column(DateTime, default=datetime.datetime.utcnow)
    health_score = Column(Float, nullable=True)  # aggregate literature-health metric


def get_session(db_url: str = DATABASE_URL):
    """WHAT: opens (and creates if needed) the database, returns a session.
    WHEN: call this once at the start of any script that reads/writes the DB."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


# ---------------------------------------------------------------------------
# CRUD helpers
# WHY these exist as functions (not inline session.add() calls scattered
# everywhere): so extraction/scoring agents don't need to know SQLAlchemy
# internals - they just call insert_claim_with_evidence(...) and it's done
# consistently every time, with the paper->claim->evidence chain always
# built correctly (claim first, flush to get its id, then evidence).
# ---------------------------------------------------------------------------

def upsert_paper(session, paper: dict, query_id: int = None):
    """WHAT: insert or update a paper row.
    WHEN: called once per paper before its claims are inserted."""
    p = session.merge(Paper(
        id=paper["id"],
        query_id=query_id,
        title=paper["title"],
        authors=paper.get("authors", ""),
        year=paper.get("year"),
        source=paper.get("source", "arXiv"),
        source_url=paper.get("source_url", f"https://arxiv.org/abs/{paper['id']}"),
    ))
    session.commit()
    return p


def insert_claim_with_evidence(session, claim_dict: dict) -> Claim:
    """WHAT: inserts one Claim row + its linked Evidence row together.
    WHY together: a claim without evidence is unverifiable and shouldn't
    exist alone in this schema (matches your workflow diagram - unverified
    claims get flagged, not silently dropped).
    Expects claim_dict keys: paper_id, claim, section, claim_type,
    source_sentence, benchmark_name (optional), reported_value (optional)."""
    claim_row = Claim(
        paper_id=claim_dict["paper_id"],
        claim_text=claim_dict["claim"],
        claim_type=claim_dict.get("claim_type"),
        section=claim_dict.get("section"),
        benchmark_name=claim_dict.get("benchmark_name"),
        reported_value=claim_dict.get("reported_value"),
        value_type=claim_dict.get("value_type"),
        evaluation_setting=claim_dict.get("evaluation_setting"),
        metric=claim_dict.get("metric"),
    )
    session.add(claim_row)
    session.flush()  # populates claim_row.id without a full commit

    session.add(Evidence(
        claim_id=claim_row.id,
        citation_text=claim_dict.get("source_sentence", ""),
    ))
    session.commit()
    return claim_row


def update_claim_score(session, claim_id: int, evidence_strength_score: float):
    """WHAT: writes the Evidence Strength Agent's output back onto a claim."""
    claim_row = session.get(Claim, claim_id)
    claim_row.evidence_strength_score = evidence_strength_score
    session.commit()


def get_all_claims_for_paper(session, paper_id: str):
    return session.query(Claim).filter(Claim.paper_id == paper_id).all()


def contradiction_exists(session, claim_a_id: int, claim_b_id: int) -> bool:
    """WHAT: checks whether this claim pair is already stored, in EITHER
    order (a,b) or (b,a).
    WHY: contradiction_agent.py can be rerun any time claims change; without
    this check, every rerun would duplicate every pair already found."""
    return session.query(Contradiction).filter(
        ((Contradiction.claim_a_id == claim_a_id) & (Contradiction.claim_b_id == claim_b_id)) |
        ((Contradiction.claim_a_id == claim_b_id) & (Contradiction.claim_b_id == claim_a_id))
    ).first() is not None


def insert_contradiction(session, claim_a_id: int, claim_b_id: int,
                          relation_type: str, severity: str = None):
    """WHAT: inserts one Contradiction row, unless this pair already exists.
    WHEN: called by contradiction_agent.py once per compared claim pair.
    Returns the new Contradiction row, or None if it was already stored
    (skip, don't duplicate)."""
    if contradiction_exists(session, claim_a_id, claim_b_id):
        return None
    row = Contradiction(
        claim_a_id=claim_a_id,
        claim_b_id=claim_b_id,
        relation_type=relation_type,
        severity=severity,
    )
    session.add(row)
    session.commit()
    return row


def get_all_contradictions(session):
    return session.query(Contradiction).all()

