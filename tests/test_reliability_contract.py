from datetime import datetime

from app.database.models import FailureCategory
from app.recovery.classifier import FailureClassifier, RecoveryPolicy, RecoveryKnowledgeBase


def test_failure_classifier_marks_timeouts_uncertain():
    err = FailureClassifier.classify("network timeout while waiting for provider", component="whatsapp", operation="send_message")
    assert err.category == FailureCategory.NETWORK_TIMEOUT.value
    assert err.retryable_hint is True
    assert err.outcome_uncertain is True


def test_retry_policy_blocks_validation_errors():
    err = FailureClassifier.classify("invalid template payload", component="whatsapp", operation="render_template")
    decision = RecoveryPolicy().decide(err, 1, action_safe_to_repeat=False)
    assert decision.retry is False
    assert decision.next_state == "NEEDS_HUMAN_REVIEW"


def test_knowledge_base_prefers_verified_strategy():
    kb = RecoveryKnowledgeBase()
    kb.upsert(component="whatsapp", operation="send_message", error_signature="RATE_LIMIT", error_category=FailureCategory.RATE_LIMIT.value, strategy_type="DELAY_AND_RETRY", strategy_config={"base_delay": 30}, status="VERIFIED")
    kb.upsert(component="whatsapp", operation="send_message", error_signature="RATE_LIMIT", error_category=FailureCategory.RATE_LIMIT.value, strategy_type="DELAY_AND_RETRY", strategy_config={"base_delay": 5}, status="PROPOSED")

    hits = kb.search(component="whatsapp", operation="send_message", error_signature="RATE_LIMIT")
    assert hits[0]["status"] == "VERIFIED"


def test_retry_policy_retries_transient_errors():
    err = FailureClassifier.classify("HTTP 429 rate limit", component="whatsapp", operation="send_message")
    decision = RecoveryPolicy().decide(err, 1, action_safe_to_repeat=True)
    assert decision.retry is True
    assert decision.delay_seconds > 0
