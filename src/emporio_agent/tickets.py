"""Support tickets: complaints and hand-offs to a human (policy §7.3 and §10).

Stored in Postgres when DATABASE_URL is configured, otherwise kept in memory.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

import psycopg

TicketKind = Literal["reclamacao", "atendimento_humano"]


@dataclass(frozen=True)
class Ticket:
    id: int
    kind: TicketKind
    summary: str
    customer_contact: str | None
    thread_id: str | None
    created_at: datetime

    @property
    def protocol(self) -> str:
        return f"EMP-{self.created_at:%Y%m%d}-{self.id:04d}"


class TicketStore(Protocol):
    def create(
        self,
        kind: TicketKind,
        summary: str,
        customer_contact: str | None,
        thread_id: str | None,
        created_at: datetime,
    ) -> Ticket: ...


class InMemoryTicketStore:
    def __init__(self) -> None:
        self.tickets: list[Ticket] = []

    def create(
        self,
        kind: TicketKind,
        summary: str,
        customer_contact: str | None,
        thread_id: str | None,
        created_at: datetime,
    ) -> Ticket:
        ticket = Ticket(
            len(self.tickets) + 1, kind, summary, customer_contact, thread_id, created_at
        )
        self.tickets.append(ticket)
        return ticket


class PostgresTicketStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id SERIAL PRIMARY KEY,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    customer_contact TEXT,
                    thread_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )

    def create(
        self,
        kind: TicketKind,
        summary: str,
        customer_contact: str | None,
        thread_id: str | None,
        created_at: datetime,
    ) -> Ticket:
        with psycopg.connect(self.database_url, autocommit=True) as conn:
            row = conn.execute(
                "INSERT INTO support_tickets"
                " (kind, summary, customer_contact, thread_id, created_at)"
                " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (kind, summary, customer_contact, thread_id, created_at),
            ).fetchone()
        return Ticket(row[0], kind, summary, customer_contact, thread_id, created_at)
