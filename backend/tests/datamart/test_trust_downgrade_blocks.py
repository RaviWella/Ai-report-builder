"""Trust level downgrade when extra blocks warn."""
from app.services.ai_services.datamart.validation.trust_scorer import (
    downgrade_overall_for_blocks,
)
from app.services.ai_services.datamart.validation.validation_models import (
    DatamartValidation,
    RetrievalValidation,
    TrustLevel,
    ValidationStatus,
)


def test_verified_downgrades_when_block_needs_review():
    base = DatamartValidation(
        retrieval=RetrievalValidation(status=ValidationStatus.SUFFICIENT),
        overall=TrustLevel.VERIFIED,
    )
    out = downgrade_overall_for_blocks(base, [TrustLevel.NEEDS_REVIEW])
    assert out.overall == TrustLevel.NEEDS_REVIEW
