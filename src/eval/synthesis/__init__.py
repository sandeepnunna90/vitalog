from src.eval.synthesis.vendor_templates.hospital import (
    generate_report as generate_hospital_report,
)
from src.eval.synthesis.vendor_templates.labcorp import (
    generate_report as generate_labcorp_report,
)
from src.eval.synthesis.vendor_templates.quest import generate_report as generate_report

__all__ = ["generate_report", "generate_hospital_report", "generate_labcorp_report"]
