import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, Float, Boolean, ForeignKey, JSON, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


class Customer(Base):
    __tablename__ = "customers"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    phone = Column(String, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    customer_id = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    status = Column(String, default="open")
    category = Column(String, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    resolution_attempts = Column(Integer, default=0)

    messages = relationship("Message", back_populates="ticket")
    resolutions = relationship("Resolution", back_populates="ticket")
    calls = relationship("Call", back_populates="ticket")


class KBArticle(Base):
    __tablename__ = "kb_articles"
    id = Column(String, primary_key=True)
    category = Column(String, nullable=False)
    subcategory = Column(String, nullable=True)
    title = Column(String, nullable=False)
    problem_variants = Column(JSON, nullable=False)
    solution_text = Column(Text, nullable=False)
    solution_steps = Column(JSON, nullable=True)
    escalate_if = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    source = Column(String, nullable=True)
    last_verified_at = Column(Date, nullable=True)


class Message(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    sender = Column(String, nullable=False)  # 'customer' | 'agent'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="messages")


class Resolution(Base):
    __tablename__ = "resolutions"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    source = Column(String, nullable=False)  # 'kb' | 'web_search' | 'human'
    kb_article_id = Column(String, ForeignKey("kb_articles.id"), nullable=True)
    web_search_log_id = Column(UUID(as_uuid=False), nullable=True)
    answer_text = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    accepted_by_customer = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="resolutions")


class Call(Base):
    __tablename__ = "calls"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    call_type = Column(String, default="confirmation")
    status = Column(String, default="scheduled")
    outcome = Column(String, nullable=True)
    provider_call_id = Column(String, nullable=True)  # Vonage call UUID
    transcript = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    retry_count = Column(Integer, default=0)  # how many prior no-answer/busy/failed attempts led to this call
    dialog_state = Column(String, default="awaiting_confirmation")  # trial-mode Gather loop state

    ticket = relationship("Ticket", back_populates="calls")


class WebSearchLog(Base):
    __tablename__ = "web_search_logs"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    query = Column(Text, nullable=False)
    source_url = Column(String, nullable=True)
    snippet = Column(Text, nullable=True)
    used_in_resolution = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    call_id = Column(UUID(as_uuid=False), ForeignKey("calls.id"), nullable=True)
    reason = Column(String, nullable=False)
    escalated_at = Column(DateTime, default=datetime.utcnow)
    assigned_agent = Column(String, nullable=True)


class StaffUser(Base):
    __tablename__ = "staff_users"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="agent")  # 'admin' | 'agent'
    created_at = Column(DateTime, default=datetime.utcnow)
