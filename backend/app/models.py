from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from .db import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    payment_id = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="failed")
    failure_reason = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    #default me sqlalchemy value generate krta h or server_default me database time set krta hai


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"))
    attempts = Column(Integer, default=0)
    status = Column(String, default="open")
    next_action_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("recovery_cases.id"))
    action_type = Column(String)
    result = Column(String)
    created_at = Column(DateTime, server_default=func.now())