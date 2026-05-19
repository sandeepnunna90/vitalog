"""Shared retry constants used by both AnthropicAdapter and TextractAdapter."""

# Sleep seconds per attempt index: 0 → 0s, 1 → 1s, 2 → 2s
ADAPTER_RETRY_SLEEP: tuple[float, ...] = (0.0, 1.0, 2.0)
