from __future__ import annotations

from typing import Any, cast

from src.gateway.gateway import Gateway
from src.ingestion.classification_schemas import Category, ClassificationResult
from src.ingestion.upload_validator import ValidatedUpload

_PDF_TEXT_LIMIT = 8_000  # chars; covers the first few pages of typical lab reports


class DocumentClassifier:
    """Classifies a ValidatedUpload into one of three categories via the AI Gateway.

    Conservative bias: if the model returns confidence < 0.70, the result is
    overridden to not_supported regardless of the original category.
    """

    def __init__(self, gateway: Gateway) -> None:
        self._gateway = gateway

    def classify(self, upload: ValidatedUpload) -> ClassificationResult:
        inputs, image_content = self._prepare_inputs(upload)
        result = cast(
            ClassificationResult,
            self._gateway.call(
                "classification",
                "v1",
                inputs,
                ClassificationResult,
                image_content=image_content,
            ),
        )
        return self._apply_conservative_bias(result)

    def _prepare_inputs(
        self, upload: ValidatedUpload
    ) -> tuple[dict[str, str], list[dict[str, Any]] | None]:
        if upload.mime == "application/pdf":
            text = self._extract_pdf_text(upload.file_bytes)
            return {"document_text": text or "[PDF has no extractable text]"}, None

        import base64

        b64 = base64.standard_b64encode(upload.file_bytes).decode()
        image_block: dict[str, Any] = {
            "type": "image",
            "source": {"type": "base64", "media_type": upload.mime, "data": b64},
        }
        return {"document_text": "Classify the provided document image."}, [image_block]

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        import fitz  # deferred; already a project dep from D1

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            parts: list[str] = []
            for page in doc:
                parts.append(page.get_text())
            return " ".join(parts)[:_PDF_TEXT_LIMIT]
        finally:
            doc.close()

    def _apply_conservative_bias(self, result: ClassificationResult) -> ClassificationResult:
        if result.confidence < 0.70:
            return ClassificationResult(
                category=Category.NOT_SUPPORTED,
                subtype=result.subtype,
                confidence=result.confidence,
                reasoning=(
                    f"Conservative bias applied (confidence {result.confidence:.2f} < 0.70). "
                    f"Original reasoning: {result.reasoning}"
                ),
            )
        return result
