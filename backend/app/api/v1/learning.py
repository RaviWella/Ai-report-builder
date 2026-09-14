"""Learning / canonical-intent governance router (#5).

Lets an HR admin govern the canonical mappings the chat has learned: list them,
CERTIFY one as the authoritative answer for a question (locked from being
overwritten by re-resolution), un-certify, or delete a wrong mapping so it is
re-derived fresh. Certifying is the trust guarantee — "this question's answer is
approved" — surfaced in the chat as a certified result.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.security import BuilderRoles, require_roles
from app.core.tenancy import TenantContext, get_tenant_context
from app.services.learning_store import LearningStore

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("", dependencies=[Depends(require_roles(*BuilderRoles))])
def list_intents(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    """Learned canonical intents for the tenant — certified first, then most-used."""
    return {"intents": LearningStore(db).list(ctx.tenant_id)}


@router.post("/{intent_id}/certify", dependencies=[Depends(require_roles(*BuilderRoles))])
def certify_intent(
    intent_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    row = LearningStore(db).set_certified(ctx.tenant_id, intent_id, True)
    if row is None:
        raise HTTPException(status_code=404, detail="Learned intent not found")
    return row


@router.post("/{intent_id}/uncertify", dependencies=[Depends(require_roles(*BuilderRoles))])
def uncertify_intent(
    intent_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    row = LearningStore(db).set_certified(ctx.tenant_id, intent_id, False)
    if row is None:
        raise HTTPException(status_code=404, detail="Learned intent not found")
    return row


@router.delete("/{intent_id}", dependencies=[Depends(require_roles(*BuilderRoles))])
def delete_intent(
    intent_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(db_session),
) -> dict:
    if not LearningStore(db).delete_by_id(ctx.tenant_id, intent_id):
        raise HTTPException(status_code=404, detail="Learned intent not found")
    return {"deleted": True}
