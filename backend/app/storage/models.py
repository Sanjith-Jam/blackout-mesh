from typing import Optional, Dict, Any, List
from sqlmodel import SQLModel, Field, Column, JSON, String
from datetime import datetime

class Run(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    site_id: str = Field(index=True)
    run_id: str = Field(index=True, unique=True)
    server_epoch: int
    started_at: datetime

class Observation(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    asset_id: str = Field(index=True)
    timestamp: datetime = Field(index=True)
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class Command(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    command_id: str = Field(index=True, unique=True)
    run_id: str = Field(index=True)
    revision: int
    timestamp: datetime
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class Decision(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    decision_id: str = Field(index=True, unique=True)
    run_id: str = Field(index=True)
    revision: int = Field(index=True)
    timestamp: datetime
    modeled_mask: int
    proposed_mask: int
    indicator_command_mask: Optional[int]
    reason: str
    context: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class Transition(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    revision: int = Field(index=True)
    timestamp: datetime
    type: str
    description: str

class Incident(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    incident_id: str = Field(index=True, unique=True)
    run_id: str = Field(index=True)
    timestamp: datetime
    code: str
    severity: str
    status: str
    evidence: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class Acknowledgment(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    device_boot: str
    sequence: int
    session: str
    timestamp: datetime
    confirmed_mask: int
