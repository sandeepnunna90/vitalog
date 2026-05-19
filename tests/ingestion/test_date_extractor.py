"""Unit tests for extract_collection_date."""

from __future__ import annotations

from datetime import date

from src.ingestion.date_extractor import extract_collection_date


def test_labcorp_date_collected() -> None:
    assert extract_collection_date("Date collected: 06/05/2019\nHbA1c: 6.8%") == date(2019, 6, 5)


def test_collection_date_label() -> None:
    assert extract_collection_date("Collection Date: 12/31/2023") == date(2023, 12, 31)


def test_date_of_service_label() -> None:
    assert extract_collection_date("Date of Service: 01/15/2022\nSomething else") == date(2022, 1, 15)


def test_specimen_collected_label() -> None:
    assert extract_collection_date("Specimen Collected: 07/04/2021") == date(2021, 7, 4)


def test_collected_short_label() -> None:
    assert extract_collection_date("Collected: 03/22/2020") == date(2020, 3, 22)


def test_drawn_label() -> None:
    assert extract_collection_date("Drawn: 11/08/2023") == date(2023, 11, 8)


def test_iso_format_after_label() -> None:
    assert extract_collection_date("Collection Date: 2019-06-05") == date(2019, 6, 5)


def test_month_name_format() -> None:
    assert extract_collection_date("Date collected: June 5, 2019") == date(2019, 6, 5)


def test_case_insensitive_label() -> None:
    assert extract_collection_date("DATE COLLECTED: 06/05/2019") == date(2019, 6, 5)


def test_labcorp_with_time_suffix_ignored() -> None:
    # LabCorp appends "0839 Local" after the date — only the date portion is captured.
    assert extract_collection_date("Date collected: 06/05/2019 0839 Local") == date(2019, 6, 5)


def test_empty_string() -> None:
    assert extract_collection_date("") is None


def test_no_date_found() -> None:
    assert extract_collection_date("HbA1c: 6.8 %\nLDL: 110 mg/dL") is None


def test_priority_first_label_wins() -> None:
    # Lower-priority label "Collected:" appears before higher-priority "Date collected:"
    # in the text — higher-priority label must win.
    text = "Collected: 01/01/2020\nDate collected: 06/05/2019\nWBC: 10.1"
    assert extract_collection_date(text) == date(2019, 6, 5)
