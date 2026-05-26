from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class AgentSummary(Base):
    __tablename__ = "agent_summaries"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(128), index=True, nullable=False)
    session_id = Column(String(128), nullable=True)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
