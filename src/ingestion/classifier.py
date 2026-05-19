from __future__ import annotations

import logging
from typing import Any

from src.gateway.gateway import Gateway
from src.ingestion.classification_schemas import Category, ClassificationResult
from src.ingestion.upload_validator import ValidatedUpload

logger = logging.getLogger(__name__)

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
        result = self._gateway.call(
            "classification",
            "v1",
            inputs,
            ClassificationResult,
            image_content=image_content,
        )
        return self._apply_conservative_bias(result)

    def _prepare_inputs(
        self, upload: ValidatedUpload
    ) -> tuple[dict[str, str], list[dict[str, Any]] | None]:
        if upload.mime == "application/pdf":
            text = self._extract_pdf_text(upload.file_bytes)
            logger.info("classifier: extracted %d chars of text from PDF", len(text))
            if text.strip():
                logger.info("classifier: using text path")
                return {"document_text": text}, None
            # No text layer (scanned PDF) — render first page and classify via vision.
            logger.info("classifier: no text extracted, attempting vision fallback")
            image_block = self._pdf_first_page_image(upload.file_bytes)
            if image_block:
                logger.info("classifier: using vision path (first page rendered)")
                return {"document_text": "Classify the provided lab report page image."}, [image_block]
            logger.info("classifier: vision render failed, using placeholder")
            return {"document_text": "[PDF has no extractable text]"}, None

        import base64

        b64 = base64.standard_b64encode(upload.file_bytes).decode()
        image_block: dict[str, Any] = {
            "type": "image",
            "source": {"type": "base64", "media_type": upload.mime, "data": b64},
        }
        return {"document_text": "Classify the provided document image."}, [image_block]

    def _pdf_first_page_image(self, file_bytes: bytes) -> dict[str, Any] | None:
        import base64
        import fitz

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            logger.info("classifier: PDF page_count=%d", doc.page_count)
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            doc.close()
        except Exception as exc:  # noqa: BLE001
            logger.info("classifier: vision render error: %s", exc)
            return None
        b64 = base64.standard_b64encode(png_bytes).decode()
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        import fitz  # deferred; already a project dep from D1

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception:  # noqa: BLE001
            return ""
        try:
            parts: list[str] = []
            total = 0
            for page in doc:
                chunk = page.get_text()
                parts.append(chunk)
                total += len(chunk)
                if total >= _PDF_TEXT_LIMIT:
                    break
            return " ".join(parts)[:_PDF_TEXT_LIMIT]
        except Exception as exc:  # noqa: BLE001
            logger.debug("PDF text extraction failed: %s", exc)
            return ""
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
