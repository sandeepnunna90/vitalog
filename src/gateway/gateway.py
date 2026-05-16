"""AI Gateway — single chokepoint for all LLM calls.

Architecture principle P3: no service may call anthropic.Anthropic() directly.
Every LLM interaction routes through Gateway.call().

Guardrail seams are overrideable methods:
  _apply_input_filters     — B2: returns log-safe (PHI-redacted) copy of inputs
  _check_injection         — B2: heuristic injection detection; returns warning or None
  _assemble_system         — B2: prepends safety preamble + few-shot refusals
  _apply_output_validators — B3/B4/B5: banned-phrase regex, schema validation, citations
  _call_with_l3_retry      — B3: one retry on BannedPhraseViolation or SchemaValidationError
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.gateway.anthropic_adapter import AnthropicAdapter
from src.gateway.errors import (
    BannedPhraseViolation,
    ModelError,
    OutputValidationError,
    SchemaValidationError,
)
from src.gateway.eval_logger import EvalLogEntry, EvalLogger, make_entry
from src.gateway.guardrails import Layer2, Layer3, detect_injection, redact_for_log
from src.gateway.prompt_registry import PromptRegistry

# AuditLogRepository is imported lazily to avoid a hard dependency on the
# persistence layer when running Gateway unit tests without Supabase.
try:
    from src.persistence.audit_log_repository import AuditLogRepository as _AuditRepo
except ImportError:  # pragma: no cover
    _AuditRepo = None  # type: ignore[assignment,misc]


class Gateway:
    def __init__(
        self,
        prompts_dir: Path | None = None,
        audit_repo: Any | None = None,  # AuditLogRepository or None
        api_key: str | None = None,
    ) -> None:
        self._registry = PromptRegistry(prompts_dir)
        self._adapter = AnthropicAdapter(api_key)
        self._logger = EvalLogger()
        self._audit = audit_repo
        self._layer2 = Layer2(prompts_dir)
        self._layer3 = Layer3(prompts_dir)

    # ── Public entry point ────────────────────────────────────────────────────

    def call(
        self,
        prompt_id: str,
        version: str,
        inputs: dict[str, Any],
        output_schema: type[BaseModel],
        *,
        image_content: list[dict[str, Any]] | None = None,
    ) -> BaseModel:
        """Invoke a registered prompt and return a validated Pydantic model.

        Raises:
            PromptNotFoundError: if prompt_id/version is not registered.
            ModelError: if the Anthropic API fails after all retries.
            OutputValidationError: if the model output fails validation.
        """
        # 1. Resolve prompt (raises PromptNotFoundError if missing — before any network call)
        tmpl = self._registry.get(prompt_id, version)

        # AC6: Validate declared output_schema_name matches the caller's schema class.
        if tmpl.output_schema_name != output_schema.__name__:
            raise OutputValidationError(
                f"Schema mismatch: prompt {prompt_id!r}@{version} declares "
                f"{tmpl.output_schema_name!r} but caller passed {output_schema.__name__!r}"
            )

        # 2. L1: Build log-safe inputs (PHI-redacted) — model sees original inputs
        log_inputs = self._apply_input_filters(inputs)

        # 3. L1: Injection check — warns and returns preamble if detected; never blocks
        injection_warning = self._check_injection(inputs)

        # 4. Render templates with ORIGINAL inputs (model sees real data)
        system_raw = tmpl.system_template.format_map(inputs)
        user_text = tmpl.user_template.format_map(inputs)

        # 5. L2: Prepend safety preamble + few-shot refusals (+ injection warning if any)
        system = self._assemble_system(system_raw, injection_warning)

        # 6. Build user content (str or list of content blocks for vision inputs)
        user_content: str | list[dict[str, Any]]
        if image_content:
            user_content = [*image_content, {"type": "text", "text": user_text}]
        else:
            user_content = user_text

        # 7. Tool-use schema from Pydantic model
        tool_name = output_schema.__name__
        tool_schema = output_schema.model_json_schema()

        # 8. Invoke model + L3 validators (with one retry on banned-phrase / schema failure)
        t0 = time.monotonic()
        raw: dict[str, Any] | None = None
        in_tok = 0
        out_tok = 0

        try:
            raw, validated, in_tok, out_tok = self._call_with_l3_retry(
                model=tmpl.model,
                system=system,
                user_content=user_content,
                tool_name=tool_name,
                tool_schema=tool_schema,
                max_tokens=tmpl.max_tokens,
                output_schema=output_schema,
            )
        except ModelError as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            self._write_eval_log(
                tmpl.prompt_id,
                tmpl.version,
                tmpl.model,
                log_inputs,
                None,
                latency_ms,
                0,
                0,
                success=False,
                error=str(exc),
            )
            raise
        except (BannedPhraseViolation, SchemaValidationError) as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            # _call_with_l3_retry attaches _retry_* attributes on the second-attempt failure
            # so the eval log captures the actual raw output and token counts.
            self._write_eval_log(
                tmpl.prompt_id,
                tmpl.version,
                tmpl.model,
                log_inputs,
                getattr(exc, "_retry_raw", raw),
                latency_ms,
                getattr(exc, "_retry_in_tok", in_tok),
                getattr(exc, "_retry_out_tok", out_tok),
                success=False,
                error=str(exc),
            )
            raise OutputValidationError(f"Output validation failed after retry: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)

        # 10. Eval log — success
        self._write_eval_log(
            tmpl.prompt_id,
            tmpl.version,
            tmpl.model,
            log_inputs,
            raw,
            latency_ms,
            in_tok,
            out_tok,
            success=True,
            error=None,
        )

        # 11. Audit log (optional — not required for unit tests without Supabase)
        if self._audit is not None:
            try:
                self._audit.record(
                    actor="system",
                    event_type="llm_call",
                    payload={
                        "prompt_id": tmpl.prompt_id,
                        "version": tmpl.version,
                        "model": tmpl.model,
                        "latency_ms": latency_ms,
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "success": True,
                    },
                )
            except Exception:  # noqa: BLE001
                pass  # audit failure must never break the caller

        return validated

    # ── Guardrail seams ───────────────────────────────────────────────────────

    def _apply_input_filters(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Return a log-safe (PHI-redacted) copy of inputs.

        The model still sees the original inputs — redaction is for logs only.
        B2: calls layer1.redact_for_log(). Overrideable for future extensions.
        """
        return redact_for_log(inputs)

    def _check_injection(self, inputs: dict[str, Any]) -> str | None:
        """Return a warning string if injection patterns detected, else None.

        The call always proceeds — detection logs a warning and returns a preamble
        that is prepended to the system prompt. Content is never dropped (§7.5).
        """
        return detect_injection(inputs)

    def _assemble_system(self, system: str, injection_warning: str | None = None) -> str:
        """Prepend safety preamble, few-shot refusals, and optional injection warning."""
        return self._layer2.augment_system(system, injection_warning)

    def _apply_output_validators(
        self, raw: dict[str, Any], output_schema: type[BaseModel]
    ) -> BaseModel:
        """B3: schema validation then banned-phrase scan via Layer3.

        Raises SchemaValidationError or BannedPhraseViolation on failure.
        B4/B5 will extend this seam with citation verification.
        """
        return self._layer3.validate_output(raw, output_schema)

    def _call_with_l3_retry(
        self,
        model: str,
        system: str,
        user_content: str | list[dict[str, Any]],
        tool_name: str,
        tool_schema: dict[str, Any],
        max_tokens: int,
        output_schema: type[BaseModel],
    ) -> tuple[dict[str, Any], BaseModel, int, int]:
        """Invoke adapter + L3 validators; retry once on L3 failure.

        Returns (raw_dict, validated_model, total_input_tokens, total_output_tokens).
        Raises ModelError if the adapter fails. Re-raises the L3 error if both attempts fail.
        """
        raw, in_tok, out_tok = self._adapter.call(
            model=model,
            system=system,
            user_content=user_content,
            tool_name=tool_name,
            tool_input_schema=tool_schema,
            max_tokens=max_tokens,
        )

        # Default: same system. Overridden below with specific guidance for each failure type.
        retry_system = system
        try:
            return raw, self._apply_output_validators(raw, output_schema), in_tok, out_tok
        except BannedPhraseViolation as exc:
            phrases_str = ", ".join(f'"{p}"' for p in exc.phrases)
            retry_system = (
                system
                + f"\n\nCRITICAL: Your previous response contained banned phrases: {phrases_str}. "
                "DO NOT use any of these phrases — this output will be rejected."
            )
        except SchemaValidationError as exc:
            field_locs = [str(e.get("loc", "")) for e in exc.field_errors[:3]]
            fields_str = ", ".join(field_locs) if field_locs else "unknown"
            hint = (
                f"\n\nCRITICAL: Previous response had missing/invalid fields: {fields_str}. "
                "Return the exact tool schema — do not omit any required fields."
            )
            retry_system = system + hint

        retry_raw, ri, ro = self._adapter.call(
            model=model,
            system=retry_system,
            user_content=user_content,
            tool_name=tool_name,
            tool_input_schema=tool_schema,
            max_tokens=max_tokens,
        )
        try:
            validated = self._apply_output_validators(retry_raw, output_schema)
            return retry_raw, validated, in_tok + ri, out_tok + ro
        except (BannedPhraseViolation, SchemaValidationError) as retry_exc:
            # Attach accounting data so gateway.call() can log the real raw/tokens.
            setattr(retry_exc, "_retry_raw", retry_raw)
            setattr(retry_exc, "_retry_in_tok", in_tok + ri)
            setattr(retry_exc, "_retry_out_tok", out_tok + ro)
            raise

    # ── Private helpers ───────────────────────────────────────────────────────

    def _write_eval_log(
        self,
        prompt_id: str,
        version: str,
        model: str,
        inputs: dict[str, Any],
        output: dict[str, Any] | None,
        latency_ms: int,
        in_tok: int,
        out_tok: int,
        success: bool,
        error: str | None,
    ) -> None:
        entry: EvalLogEntry = make_entry(
            prompt_id=prompt_id,
            version=version,
            model=model,
            inputs_redacted=inputs,
            output=output,
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            success=success,
            error=error,
        )
        try:
            self._logger.log(entry)
        except Exception:  # noqa: BLE001
            pass  # eval log failure must never break the caller
