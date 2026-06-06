import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Text, Integer, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Use SQLite for local development
    DATABASE_URL = "sqlite:///titan_dev.db"

# Create Database Engine
engine = create_engine(
    DATABASE_URL, 
    # Disable pool_pre_ping for SQLite, enable for Postgres
    pool_pre_ping=True if DATABASE_URL.startswith("postgresql") else False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ComplianceRule(Base):
    __tablename__ = "compliance_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_text = Column(Text, nullable=False)
    severity = Column(String(50), default="hard_block") # 'hard_block' | 'warning'
    created_at = Column(DateTime, default=datetime.utcnow)

class Negotiation(Base):
    __tablename__ = "negotiations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    supplier_id = Column(String(50), nullable=False)
    risk_signal = Column(JSON, nullable=True)
    impact_report = Column(JSON, nullable=True)
    draft_body = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True) # JSON serialized float array for pgvector portability
    outcome = Column(String(50), default="pending") # 'sent' | 'rejected' | 'discarded' | 'pending'
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Seed rules if compliance_rules is empty
    session = SessionLocal()
    try:
        if session.query(ComplianceRule).count() == 0:
            rules = [
                ComplianceRule(
                    rule_text="Do not promise or lock fixed pricing for a period exceeding 12 months.",
                    severity="hard_block"
                ),
                ComplianceRule(
                    rule_text="Do not include any language offering gifts, kickbacks, incentives, gratuities, or informal side-deals.",
                    severity="hard_block"
                ),
                ComplianceRule(
                    rule_text="Ensure anti-bribery policies are respected: all transactions must be transparent and documented.",
                    severity="hard_block"
                ),
                ComplianceRule(
                    rule_text="Avoid aggressive or hostile language; keep email tone collaborative, professional, and firm.",
                    severity="warning"
                ),
                ComplianceRule(
                    rule_text="Do not disclose specific margins of other competitive suppliers in the email.",
                    severity="hard_block"
                )
            ]
            session.add_all(rules)
            session.commit()
            print("Successfully initialized and seeded compliance rules!")
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
    finally:
        session.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_text_embedding(text: str) -> list:
    import hashlib
    vector = [0.0] * 1536
    words = text.lower().split()
    if not words:
        return vector
    for word in words:
        h = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16)
        bucket = h % 1536
        sign = 1 if (h % 2) == 0 else -1
        vector[bucket] += sign
    norm = sum(x * x for x in vector) ** 0.5
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector

# Helper for vector similarity in Python (for SQLite/Postgres portability)
def cosine_similarity(v1, v2):
    if not v1 or not v2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = sum(a * a for a in v1) ** 0.5
    norm_b = sum(b * b for b in v2) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def find_similar_negotiations(db_session, target_embedding, supplier_id=None, limit=3):
    """
    Retrieves negotiations from history and ranks them by cosine similarity of embeddings.
    """
    query = db_session.query(Negotiation)
    if supplier_id:
        query = query.filter(Negotiation.supplier_id == supplier_id)
        
    records = query.all()
    if not records or not target_embedding:
        return []
        
    scored_records = []
    for rec in records:
        if not rec.embedding:
            continue
        try:
            emb = json.loads(rec.embedding)
            sim = cosine_similarity(target_embedding, emb)
            scored_records.append((rec, sim))
        except Exception:
            continue
            
    # Sort by similarity descending
    scored_records.sort(key=lambda x: x[1], reverse=True)
    return scored_records[:limit]
