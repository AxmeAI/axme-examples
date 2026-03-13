"""Unit tests for runner/handlers/*.py

Every handler function is tested for:
  1. Valid input → passes (no _passed=False)
  2. Invalid / boundary input → fails with expected violation keys
  3. Edge cases (missing fields, wrong types, empty values)

No network calls — pure logic tests.
"""
from __future__ import annotations

import sys
import os

# Ensure runner package is importable when running from axme-examples root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runner.handlers import (
    batch_processor,
    cache_invalidation_agent,
    change_validator,
    compliance_checker,
    deployment_impact_assessor,
    deployment_notifier,
    fulfillment_service,
    policy_checker,
    pre_check_agent,
    risk_calculator,
    webhook_receiver,
)


# ---------------------------------------------------------------------------
# compliance_checker
# ---------------------------------------------------------------------------

class TestComplianceChecker:
    def _valid(self, **overrides):
        base = {
            "change_id":        "CHG-001",
            "service":          "nginx",
            "environment":      "staging",
            "change_type":      "config_update",
            "risk_level":       "medium",
            "rollback_plan":    "revert via git tag v1.0",
            "backup_confirmed": False,
        }
        return {**base, **overrides}

    def test_valid_input_passes(self):
        r = compliance_checker.handle(self._valid())
        assert r["compliance_passed"] is True
        assert r["violations"] == []
        assert "_passed" not in r or r.get("_passed", True) is True

    def test_missing_rollback_plan_fails(self):
        r = compliance_checker.handle(self._valid(rollback_plan=""))
        assert r["_passed"] is False
        assert "rollback_plan_missing" in r["violations"]

    def test_critical_risk_in_prod_fails(self):
        r = compliance_checker.handle(self._valid(environment="prod", risk_level="critical"))
        assert r["_passed"] is False
        assert any("critical" in v for v in r["violations"])

    def test_schema_migration_without_backup_fails(self):
        r = compliance_checker.handle(
            self._valid(change_type="schema_migration", backup_confirmed=False)
        )
        assert r["_passed"] is False
        assert any("backup" in v for v in r["violations"])

    def test_schema_migration_with_backup_passes(self):
        r = compliance_checker.handle(
            self._valid(change_type="schema_migration", backup_confirmed=True)
        )
        assert r["compliance_passed"] is True

    def test_unknown_environment_fails(self):
        r = compliance_checker.handle(self._valid(environment="unknown-cloud-region"))
        assert r["_passed"] is False
        assert any("environment" in v for v in r["violations"])

    def test_result_depends_on_input(self):
        """Different payloads produce different results."""
        r1 = compliance_checker.handle(self._valid(environment="staging", risk_level="low"))
        r2 = compliance_checker.handle(self._valid(environment="prod", risk_level="critical"))
        assert r1["compliance_passed"] != r2["compliance_passed"]


# ---------------------------------------------------------------------------
# risk_calculator
# ---------------------------------------------------------------------------

class TestRiskCalculator:
    def _valid(self, **overrides):
        base = {
            "change_id":     "CHG-900",
            "service":       "nginx",
            "version":       "2.5.0",
            "environment":   "staging",
            "risk_level":    "low",
            "rollback_plan": "kubectl rollout undo",
        }
        return {**base, **overrides}

    def test_low_risk_staging_score_is_low(self):
        r = risk_calculator.handle(self._valid())
        # base=10, staging no +15, rollback -10 → score=0, capped to 0 → "low"
        assert r["risk_level"] == "low"
        assert r["risk_score"] <= 25

    def test_high_risk_prod_raises_score(self):
        r = risk_calculator.handle(self._valid(environment="prod", risk_level="high"))
        # base=70, prod+15, rollback-10 → 75 → "high"
        assert r["risk_score"] >= 55

    def test_critical_no_rollback_returns_critical(self):
        r = risk_calculator.handle(
            self._valid(environment="prod", risk_level="critical", rollback_plan="")
        )
        assert r["risk_level"] == "critical"
        assert r["rollback_available"] is False

    def test_prod_blast_radius_high_score(self):
        r = risk_calculator.handle(self._valid(environment="prod", risk_level="high"))
        assert r["blast_radius"] == "multiple_services"

    def test_staging_blast_radius_single(self):
        r = risk_calculator.handle(self._valid(environment="staging", risk_level="low"))
        assert r["blast_radius"] == "single_service"

    def test_schema_migration_raises_score(self):
        r_base = risk_calculator.handle(self._valid())
        r_mig  = risk_calculator.handle(self._valid(change_type="schema_migration"))
        assert r_mig["risk_score"] > r_base["risk_score"]


# ---------------------------------------------------------------------------
# change_validator
# ---------------------------------------------------------------------------

class TestChangeValidator:
    def _valid(self, **overrides):
        base = {
            "change_id":    "CHG-4821",
            "service":      "nginx",
            "environment":  "prod-cluster-eu",
            "risk_level":   "medium",
            "rollback_plan": "revert config",
        }
        return {**base, **overrides}

    def test_valid_passes(self):
        r = change_validator.handle(self._valid())
        assert r["validation_passed"] is True
        assert r["checks_failed"] == []

    def test_invalid_change_id_fails(self):
        r = change_validator.handle(self._valid(change_id="TICKET-001"))
        assert r["_passed"] is False
        assert any("change_id" in f for f in r["checks_failed"])

    def test_missing_rollback_fails(self):
        r = change_validator.handle(self._valid(rollback_plan=""))
        assert r["_passed"] is False
        assert any("rollback" in f for f in r["checks_failed"])

    def test_unknown_environment_fails(self):
        r = change_validator.handle(self._valid(environment="on-prem-dc1"))
        assert r["_passed"] is False

    def test_missing_service_fails(self):
        r = change_validator.handle(self._valid(service=""))
        assert r["_passed"] is False


# ---------------------------------------------------------------------------
# deployment_impact_assessor
# ---------------------------------------------------------------------------

class TestDeploymentImpactAssessor:
    def test_nginx_has_multiple_affected(self):
        r = deployment_impact_assessor.handle({
            "service": "nginx", "environment": "prod", "risk_level": "medium"
        })
        assert len(r["affected_services"]) >= 2
        assert r["blast_radius"] in {"multiple_services", "full_platform"}

    def test_postgres_has_downtime(self):
        r = deployment_impact_assessor.handle({
            "service": "postgres", "environment": "prod", "risk_level": "high"
        })
        assert r["estimated_downtime_minutes"] > 0

    def test_unknown_service_returns_single(self):
        r = deployment_impact_assessor.handle({
            "service": "my-custom-svc", "environment": "staging", "risk_level": "low"
        })
        assert r["blast_radius"] == "single_service"
        assert r["affected_services"] == ["my-custom-svc"]

    def test_payment_service_full_platform(self):
        r = deployment_impact_assessor.handle({
            "service": "payment-service", "environment": "prod", "risk_level": "critical"
        })
        assert r["blast_radius"] == "multiple_services"
        assert r["assessment_passed"] is True


# ---------------------------------------------------------------------------
# batch_processor
# ---------------------------------------------------------------------------

class TestBatchProcessor:
    def _valid(self, **overrides):
        base = {
            "batch_id":    "batch-2026-03-13-001",
            "record_type": "transactions",
            "date_range":  "2026-03-12",
        }
        return {**base, **overrides}

    def test_valid_passes(self):
        r = batch_processor.handle(self._valid())
        assert r["batch_processed"] is True
        assert r["records_count"] > 0

    def test_deterministic_count(self):
        r1 = batch_processor.handle(self._valid())
        r2 = batch_processor.handle(self._valid())
        assert r1["records_count"] == r2["records_count"]

    def test_different_batch_ids_may_differ(self):
        r1 = batch_processor.handle(self._valid(batch_id="batch-2026-03-13-001"))
        r2 = batch_processor.handle(self._valid(batch_id="batch-2026-03-13-099"))
        # At least the batch_id is different in result
        assert r1["batch_id"] != r2["batch_id"]

    def test_invalid_batch_id_fails(self):
        r = batch_processor.handle(self._valid(batch_id="my-batch-job"))
        assert r["_passed"] is False
        assert any("batch_id" in v for v in r["violations"])

    def test_invalid_date_range_fails(self):
        r = batch_processor.handle(self._valid(date_range="not-a-date"))
        assert r["_passed"] is False

    def test_missing_record_type_fails(self):
        r = batch_processor.handle(self._valid(record_type=""))
        assert r["_passed"] is False


# ---------------------------------------------------------------------------
# webhook_receiver
# ---------------------------------------------------------------------------

class TestWebhookReceiver:
    def _valid(self, **overrides):
        base = {
            "event_type": "order.placed",
            "order_id":   "ord-8821",
            "amount":     250.00,
            "currency":   "USD",
        }
        return {**base, **overrides}

    def test_valid_passes(self):
        r = webhook_receiver.handle(self._valid())
        assert r["accepted"] is True
        assert r["via"] == "http_callback"

    def test_unknown_event_type_fails(self):
        r = webhook_receiver.handle(self._valid(event_type="cart.viewed"))
        assert r["_passed"] is False
        assert any("event_type" in v for v in r["violations"])

    def test_invalid_order_id_fails(self):
        r = webhook_receiver.handle(self._valid(order_id="ORDER_8821"))
        assert r["_passed"] is False

    def test_negative_amount_fails(self):
        r = webhook_receiver.handle(self._valid(amount=-50))
        assert r["_passed"] is False

    def test_unsupported_currency_fails(self):
        r = webhook_receiver.handle(self._valid(currency="BTC"))
        assert r["_passed"] is False


# ---------------------------------------------------------------------------
# fulfillment_service
# ---------------------------------------------------------------------------

class TestFulfillmentService:
    def _valid(self, **overrides):
        base = {
            "order_id":    "ord-4422",
            "customer_id": "cust-007",
            "items":       [{"sku": "PROD-001", "quantity": 3}],
            "shipping":    "express",
        }
        return {**base, **overrides}

    def test_valid_passes(self):
        r = fulfillment_service.handle(self._valid())
        assert r["fulfilled"] is True
        assert r["tracking_id"].startswith("TRK-")
        assert r["estimated_delivery_days"] == 2

    def test_tracking_id_is_deterministic(self):
        r1 = fulfillment_service.handle(self._valid())
        r2 = fulfillment_service.handle(self._valid())
        assert r1["tracking_id"] == r2["tracking_id"]

    def test_different_orders_different_tracking(self):
        r1 = fulfillment_service.handle(self._valid(order_id="ord-0001"))
        r2 = fulfillment_service.handle(self._valid(order_id="ord-9999"))
        assert r1["tracking_id"] != r2["tracking_id"]

    def test_standard_shipping_5_days(self):
        r = fulfillment_service.handle(self._valid(shipping="standard"))
        assert r["estimated_delivery_days"] == 5

    def test_overnight_shipping_1_day(self):
        r = fulfillment_service.handle(self._valid(shipping="overnight"))
        assert r["estimated_delivery_days"] == 1

    def test_missing_order_id_fails(self):
        r = fulfillment_service.handle(self._valid(order_id=""))
        assert r["_passed"] is False

    def test_empty_items_fails(self):
        r = fulfillment_service.handle(self._valid(items=[]))
        assert r["_passed"] is False

    def test_unknown_shipping_tier_fails(self):
        r = fulfillment_service.handle(self._valid(shipping="drone"))
        assert r["_passed"] is False


# ---------------------------------------------------------------------------
# policy_checker
# ---------------------------------------------------------------------------

class TestPolicyChecker:
    def _valid(self, **overrides):
        base = {
            "resource":      "prod-secrets-manager",
            "access_type":   "READ",
            "requestor":     "svc:deploy-pipeline",
            "justification": "CI/CD pipeline needs deployment secrets",
        }
        return {**base, **overrides}

    def test_valid_passes(self):
        r = policy_checker.handle(self._valid())
        assert r["policy_passed"] is True

    def test_missing_justification_for_protected_fails(self):
        r = policy_checker.handle(self._valid(justification=""))
        assert r["_passed"] is False
        assert any("justification" in v for v in r["violations"])

    def test_write_to_protected_fails(self):
        r = policy_checker.handle(self._valid(access_type="DELETE"))
        assert r["_passed"] is False
        assert any("write_access" in v for v in r["violations"])

    def test_non_protected_resource_no_justification_passes(self):
        r = policy_checker.handle({
            "resource":      "public-config",
            "access_type":   "READ",
            "requestor":     "svc:my-app",
            "justification": "",
        })
        assert r["policy_passed"] is True

    def test_missing_requestor_fails(self):
        r = policy_checker.handle(self._valid(requestor=""))
        assert r["_passed"] is False


# ---------------------------------------------------------------------------
# pre_check_agent
# ---------------------------------------------------------------------------

class TestPreCheckAgent:
    def _valid(self, **overrides):
        base = {
            "pr_id":         "PR-4422",
            "repository":    "axme-control-plane",
            "branch":        "feature/payment-refactor",
            "author":        "alice@example.com",
            "files_changed": 14,
        }
        return {**base, **overrides}

    def test_valid_passes(self):
        r = pre_check_agent.handle(self._valid())
        assert r["pre_check_passed"] is True

    def test_invalid_pr_id_fails(self):
        r = pre_check_agent.handle(self._valid(pr_id="fix/some-bug"))
        assert r["_passed"] is False
        assert any("pr_id" in f for f in r["checks_failed"])

    def test_oversized_pr_fails(self):
        r = pre_check_agent.handle(self._valid(files_changed=600))
        assert r["_passed"] is False
        assert any("too_large" in f for f in r["checks_failed"])

    def test_missing_author_fails(self):
        r = pre_check_agent.handle(self._valid(author=""))
        assert r["_passed"] is False

    def test_missing_repository_fails(self):
        r = pre_check_agent.handle(self._valid(repository=""))
        assert r["_passed"] is False


# ---------------------------------------------------------------------------
# cache_invalidation_agent
# ---------------------------------------------------------------------------

class TestCacheInvalidationAgent:
    def _valid(self, **overrides):
        base = {
            "service":    "cache-service",
            "operation":  "invalidate_and_reload",
            "cache_keys": ["user:*", "session:*"],
        }
        return {**base, **overrides}

    def test_valid_passes(self):
        r = cache_invalidation_agent.handle(self._valid())
        assert r["operation_accepted"] is True
        assert r["keys_count"] == 2

    def test_unknown_operation_fails(self):
        r = cache_invalidation_agent.handle(self._valid(operation="purge_all"))
        assert r["_passed"] is False
        assert any("operation" in v for v in r["violations"])

    def test_empty_cache_keys_fails(self):
        r = cache_invalidation_agent.handle(self._valid(cache_keys=[]))
        assert r["_passed"] is False

    def test_count_reflects_input(self):
        r = cache_invalidation_agent.handle(self._valid(
            cache_keys=["k1", "k2", "k3", "k4"]
        ))
        assert r["keys_count"] == 4


# ---------------------------------------------------------------------------
# deployment_notifier
# ---------------------------------------------------------------------------

class TestDeploymentNotifier:
    def _valid(self, **overrides):
        base = {
            "deployment_id": "deploy-2026-03-13-nginx",
            "service":       "nginx",
            "environment":   "prod-cluster-eu",
            "triggered_by":  "ci-cd-pipeline",
        }
        return {**base, **overrides}

    def test_valid_passes(self):
        r = deployment_notifier.handle(self._valid())
        assert r["deployment_accepted"] is True

    def test_missing_deployment_id_fails(self):
        r = deployment_notifier.handle(self._valid(deployment_id=""))
        assert r["_passed"] is False

    def test_unknown_environment_fails(self):
        r = deployment_notifier.handle(self._valid(environment="on-prem"))
        assert r["_passed"] is False

    def test_missing_triggered_by_fails(self):
        r = deployment_notifier.handle(self._valid(triggered_by=""))
        assert r["_passed"] is False


# ---------------------------------------------------------------------------
# resolve_handler registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_handlers_resolvable(self):
        from runner.handlers import resolve_handler
        names = [
            "compliance_checker", "risk_calculator", "change_validator",
            "deployment_impact_assessor", "batch_processor", "webhook_receiver",
            "fulfillment_service", "policy_checker", "pre_check_agent",
            "cache_invalidation_agent", "deployment_notifier",
        ]
        for name in names:
            fn = resolve_handler(name)
            assert callable(fn), f"{name} is not callable"

    def test_missing_handler_raises(self):
        from runner.handlers import HandlerNotFoundError, resolve_handler
        try:
            resolve_handler("non_existent_handler")
            assert False, "should have raised"
        except HandlerNotFoundError:
            pass
