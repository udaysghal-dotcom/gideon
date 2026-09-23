"""
Clean every ADR sheet in the ADR database into one CSV per ADR.

Usage:
    python3 db/parse_adr.py [--input (location of ADR_Database.xlsx file)] [--output (where you want to put data files)]
    ex: python3 db/parse_adr.py --input db/ADR_Database.xlsx --ouput db/data
"""

import argparse
import csv
import re
import sys
import warnings
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "ADR_Database.xlsx"
DEFAULT_OUTPUT = ROOT / "data"

SHEET_PATTERN = re.compile(r"ADR\s*(\d+)", re.IGNORECASE)
PROJECT_ID_PATTERN = re.compile(r"SRP8-(\d{1,3})", re.IGNORECASE)
EXCEL_ERRORS = {"#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NULL!", "#NUM!"}
NOT_APPLICABLE = {"N/A", "NA", "-"}

OUTPUT_COLUMNS = ["Checklist", "Clause", "Req Name", "Details", "Project ID", "Verification Method"]


def clean(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    lines = (" ".join(line.split()) for line in str(value).splitlines())
    text = "\n".join(line for line in lines if line)
    return "" if text.upper() in EXCEL_ERRORS else text


def clean_clause(value):
    clause = clean(value)
    if re.fullmatch(r"[\d.]+\.", clause):
        clause = clause.rstrip(".")
    return clause


def clean_project_id(value, sheet, warn):
    project_id = clean(value)
    if project_id.upper() in NOT_APPLICABLE:
        return ""
    match = PROJECT_ID_PATTERN.fullmatch(project_id)
    if match:
        return f"SRP8-{int(match.group(1)):03d}"
    if project_id:
        warn(f"{sheet}: unrecognised Project ID {project_id!r}")
    return project_id


def checklist_number(value):
    text = clean(value)
    return int(text) if text.isdigit() else None


def find_columns(header, sheet):
    names = [clean(name) for name in header]

    def index_of(predicate):
        return next((i for i, name in enumerate(names) if predicate(name)), None)

    columns = {
        "clause": index_of(lambda name: name == "Clause"),
        "name": index_of(lambda name: name == "Req Name"),
        "project": index_of(lambda name: name == "Project ID"),
        "verification": index_of(
            lambda name: name.startswith("Verification Method") and "Description" not in name
        ),
        "text": index_of(lambda name: name == "Text"),
        "checklist": index_of(lambda name: name == "Checklist"),
    }
    if columns["text"] is None and columns["name"] is not None:
        columns["text"] = columns["name"] + 1
    if columns["checklist"] is None and 0 not in columns.values():
        columns["checklist"] = 0

    missing = [key for key in ("clause", "name", "project", "verification", "text") if columns[key] is None]
    if missing:
        raise ValueError(f"{sheet}: could not find columns {missing} in header {names}")
    return columns


def fill_checklist(rows):
    numbers = [checklist_number(row["Checklist"]) for row in rows]
    next_number = max((n for n in numbers if n is not None), default=0) + 1
    for row, number in zip(rows, numbers):
        if number is None:
            number = next_number
            next_number += 1
        row["Checklist"] = str(number)


def parse_sheet(sheet, warn):
    rows = sheet.iter_rows(values_only=True)
    header = next(rows, None)
    if header is None:
        return []
    columns = find_columns(header, sheet.title)

    def cell(row, key):
        index = columns[key]
        return row[index] if index is not None and index < len(row) else None

    cleaned = []
    for row in rows:
        record = {
            "Checklist": clean(cell(row, "checklist")),
            "Clause": clean_clause(cell(row, "clause")),
            "Req Name": clean(cell(row, "name")),
            "Details": clean(cell(row, "text")),
            "Project ID": clean_project_id(cell(row, "project"), sheet.title, warn),
            "Verification Method": clean(cell(row, "verification")),
        }
        if not record["Details"] and not record["Project ID"]:
            continue
        cleaned.append(record)

    fill_checklist(cleaned)
    return cleaned


def adr_sheets(workbook):
    for sheet in workbook.worksheets:
        match = SHEET_PATTERN.fullmatch(sheet.title.strip())
        if match:
            yield int(match.group(1)), sheet


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="ADR database workbook")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="directory for cleaned CSVs")
    args = parser.parse_args()

    def warn(message):
        print(f"warning: {message}", file=sys.stderr)

    warnings.filterwarnings("ignore", message="Data Validation extension is not supported")
    workbook = load_workbook(args.input, read_only=True, data_only=True)

    args.output.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        for number, sheet in adr_sheets(workbook):
            rows = parse_sheet(sheet, warn)
            path = args.output / f"adr_{number:02d}.csv"
            write_csv(path, rows)
            total += len(rows)
            print(f"{sheet.title:>8} -> {path.relative_to(args.output.parent)} ({len(rows)} requirements)")
    finally:
        workbook.close()
    print(f"Wrote {total} requirements")


if __name__ == "__main__":
    main()
