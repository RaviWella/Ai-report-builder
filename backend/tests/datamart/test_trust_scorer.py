"""Trust level computation."""
from app.services.ai_services.datamart.validation.trust_scorer import compute_trust_level
from app.services.ai_services.datamart.validation.validation_models import (
    GenerationValidation,
    RetrievalValidation,
    TrustLevel,
    ValidationStatus,
)


def test_verified_when_clean():
    retrieval = RetrievalValidation(status=ValidationStatus.SUFFICIENT)
    generation = GenerationValidation(binding="passed", warnings=[])
    assert compute_trust_level(retrieval=retrieval, generation=generation) == TrustLevel.VERIFIED


def test_needs_review_on_faithfulness_warning():
    retrieval = RetrievalValidation(status=ValidationStatus.SUFFICIENT)
    generation = GenerationValidation(
        binding="passed",
        warnings=["LIMIT mismatch"],
    )
    assert compute_trust_level(retrieval=retrieval, generation=generation) == TrustLevel.NEEDS_REVIEW


def test_blocked_on_error():
    retrieval = RetrievalValidation(status=ValidationStatus.SUFFICIENT)
    assert compute_trust_level(retrieval=retrieval, generation=None, error="fail") == TrustLevel.BLOCKED
