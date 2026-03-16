"""Handler registry — maps handler names to real agent logic functions.

Each handler function has the signature:
    def handle(payload: dict) -> dict

Return value rules:
    - Include ``_passed: False`` to signal FAILED resume; omit (or True) for COMPLETED.
    - For failure, include ``reason`` key.
    - All other keys are forwarded as-is to resume_intent().
    - Never return hardcoded outcomes — the result must depend on the input payload.
"""
from __future__ import annotations

from typing import Any, Callable

from . import (
    batch_processor,
    cache_invalidation_agent,
    change_validator,
    compliance_checker,
    deployment_impact_assessor,
    deployment_notifier,
    fulfillment_service,
    order_executor,
    order_validator,
    policy_checker,
    pre_check_agent,
    risk_calculator,
    simple_echo,
    webhook_receiver,
)

_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "compliance_checker": compliance_checker.handle,
    "risk_calculator": risk_calculator.handle,
    "change_validator": change_validator.handle,
    "deployment_impact_assessor": deployment_impact_assessor.handle,
    "batch_processor": batch_processor.handle,
    "webhook_receiver": webhook_receiver.handle,
    "fulfillment_service": fulfillment_service.handle,
    "policy_checker": policy_checker.handle,
    "pre_check_agent": pre_check_agent.handle,
    "cache_invalidation_agent": cache_invalidation_agent.handle,
    "deployment_notifier": deployment_notifier.handle,
    "simple_echo": simple_echo.handle,
    "order_validator": order_validator.handle,
    "order_executor": order_executor.handle,
}


class HandlerNotFoundError(KeyError):
    """Raised when no handler is registered for the given name."""


def resolve_handler(name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return the handler function for the given name.

    Raises:
        HandlerNotFoundError: If no handler is registered under ``name``.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY))
        raise HandlerNotFoundError(
            f"no handler registered for '{name}'. Available: {available}"
        )


__all__ = ["resolve_handler", "HandlerNotFoundError"]
