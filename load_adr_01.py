import csv
import os
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "gideon database"
ADR_CODE = "ADR-01"
ADR_COLUMNS = ["1st ADR", "2nd ADR", "3rd ADR", "4th ADR", "5th ADR", "6th ADR"]


def load_env(path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def blank_to_none(value):
    value = (value or "").strip()
    return value or None


def adr_links():
    links = []
    with (DATA / "project_adr_map_clean.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            project_id = row["Project ID"].strip()
            for column in ADR_COLUMNS:
                if (row.get(column) or "").strip() == ADR_CODE:
                    links.append({"projectId": project_id, "source": column})
    if not links:
        raise SystemExit(f"No project in the map lists {ADR_CODE}")
    return links


def requirements():
    path = DATA / "adr_01_clean.csv"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        verification_column = next(
            name for name in reader.fieldnames if name.startswith("Verification Method")
        )
        rows = []
        for row in reader:
            rows.append(
                {
                    "checklist": row["Checklist"].strip(),
                    "clause": row["Clause"].strip(),
                    "name": blank_to_none(row["Req Name"]),
                    "details": blank_to_none(row["Details"]),
                    "projectId": row["Project ID"].strip(),
                    "project": blank_to_none(row["Relevant Project"]),
                    "department": blank_to_none(row["Relevant Department"]),
                    "verification": blank_to_none(row[verification_column]),
                }
            )
    return rows


def main():
    load_env(ROOT / ".env")
    links = adr_links()
    rows = requirements()
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    query = """
    MERGE (a:ADR {code: $adrCode})
    WITH a
    UNWIND $links AS link
    MATCH (p:project_adr_map {`Project ID`: link.projectId})
    MERGE (p)-[rel:HAS_ADR]->(a)
    SET rel.source = link.source
    WITH a
    UNWIND $rows AS row
    MERGE (req:Requirement {adr: $adrCode, checklist: row.checklist, clause: row.clause})
    SET req.name = row.name,
        req.details = row.details,
        req.projectId = row.projectId,
        req.project = row.project,
        req.department = row.department,
        req.verification = row.verification
    MERGE (a)-[:HAS_REQUIREMENT]->(req)
    RETURN count(req) AS requirements
    """
    try:
        with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
            record = session.run(
                query, adrCode=ADR_CODE, links=links, rows=rows
            ).single()
            print(f"Linked {record['requirements']} requirements to {ADR_CODE}")
            print("Projects:", ", ".join(link["projectId"] for link in links))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
