"""
Apply schema.cypher and load the cleaned ADR data into Neo4j.

Reads project_adr_map_clean.csv and every adr_XX.csv in the data directory.
Don't forget to load Neo4j credentials into .env file

Usage:
    python3 db/scripts/load_graph.py [--data (directory of cleaned csvs)] [--reset] [--dry-run]
    ex: python3 db/scripts/load_graph.py --data db/adr_data --reset
"""

import argparse
import csv
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE.parent
REPO = DB.parent
DEFAULT_DATA = DB / "adr_data"
SCHEMA_FILE = DB / "schema" / "schema.cypher"
MAP_FILE = "project_adr_map_clean.csv"
ADR_FILE_GLOB = "adr_*.csv"

PROJECT_ID_PATTERN = re.compile(r"SRP8-\d{3}")
ADR_PATTERN = re.compile(r"ADR[-_]0*(\d+)", re.IGNORECASE)
NOT_APPLICABLE = {"N/A", "NA", "-"}
GRAPH_LABELS = ["Project", "Department", "ADR", "Requirement", "project_adr_map"]


def load_env(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def text(value):
    value = " ".join((value or "").split())
    return "" if value.upper() in NOT_APPLICABLE else value


def adr_code(value):
    match = ADR_PATTERN.search(value or "")
    if not match:
        return None
    number = int(match.group(1))
    return f"ADR-{number:02d}", number


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def parse_project_map(path, warn):
    columns, rows = read_csv(path)
    department_columns = [name for name in columns if name.endswith("Department")]
    adr_columns = [name for name in columns if name.endswith("ADR")]

    projects, departments, adr_links, adrs = [], [], {}, {}
    for row in rows:
        project_id = text(row.get("Project ID"))
        if not PROJECT_ID_PATTERN.fullmatch(project_id):
            warn(f"{path.name}: skipping row with Project ID {project_id!r}")
            continue
        projects.append({"id": project_id, "name": text(row.get("Project Name")) or None})

        for column in department_columns:
            name = text(row.get(column))
            if name:
                role = column.split()[0].lower()
                departments.append({"projectId": project_id, "name": name, "role": role})

        for rank, column in enumerate(adr_columns, start=1):
            parsed = adr_code(row.get(column))
            if not parsed:
                if text(row.get(column)):
                    warn(f"{path.name}: {project_id} has unrecognised {column} {row[column]!r}")
                continue
            code, number = parsed
            adrs[code] = number
            adr_links.setdefault((project_id, code), []).append(rank)

    links = [
        {"projectId": project_id, "code": code, "rank": ranks[0], "ranks": ranks}
        for (project_id, code), ranks in adr_links.items()
    ]
    return projects, departments, links, adrs


def parse_requirements(data_dir, warn):
    requirements, verifications, adrs = {}, {}, {}
    for path in sorted(data_dir.glob(ADR_FILE_GLOB)):
        parsed = adr_code(path.stem)
        if not parsed:
            warn(f"{path.name}: cannot infer an ADR code from the file name, skipping")
            continue
        code, number = parsed
        adrs[code] = number

        _, rows = read_csv(path)
        for row in rows:
            checklist = text(row.get("Checklist"))
            clause = text(row.get("Clause"))
            name = text(row.get("Req Name"))
            if not (checklist or clause or name):
                continue
            requirement_id = "|".join([code, checklist, clause, name])
            requirements.setdefault(requirement_id, {
                "id": requirement_id,
                "adr": code,
                "checklist": checklist or None,
                "clause": clause or None,
                "name": name or None,
                "details": (row.get("Details") or "").strip() or None,
            })

            project_id = text(row.get("Project ID"))
            if not project_id:
                continue
            if not PROJECT_ID_PATTERN.fullmatch(project_id):
                warn(f"{path.name}: checklist {checklist} has invalid Project ID {project_id!r}")
                continue
            verifications[(requirement_id, project_id)] = {
                "requirementId": requirement_id,
                "projectId": project_id,
                "method": text(row.get("Verification Method")) or None,
            }
    return list(requirements.values()), list(verifications.values()), adrs


def schema_statements(path):
    lines = [line for line in path.read_text().splitlines() if not line.strip().startswith("//")]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


LOAD_QUERIES = [
    (
        "projects",
        "projects",
        """
        UNWIND $rows AS row
        MERGE (p:Project {id: row.id})
        SET p.name = row.name
        """,
    ),
    (
        "departments",
        "departments",
        """
        UNWIND $rows AS row
        MATCH (p:Project {id: row.projectId})
        MERGE (d:Department {name: row.name})
        MERGE (p)-[:IN_DEPARTMENT {role: row.role}]->(d)
        """,
    ),
    (
        "ADRs",
        "adrs",
        """
        UNWIND $rows AS row
        MERGE (a:ADR {code: row.code})
        SET a.number = row.number
        """,
    ),
    (
        "project-ADR links",
        "adr_links",
        """
        UNWIND $rows AS row
        MATCH (p:Project {id: row.projectId})
        MATCH (a:ADR {code: row.code})
        MERGE (p)-[rel:MUST_COMPLY_WITH]->(a)
        SET rel.rank = row.rank, rel.ranks = row.ranks
        """,
    ),
    (
        "requirements",
        "requirements",
        """
        UNWIND $rows AS row
        MATCH (a:ADR {code: row.adr})
        MERGE (r:Requirement {id: row.id})
        SET r.adr = row.adr,
            r.checklist = row.checklist,
            r.clause = row.clause,
            r.name = row.name,
            r.details = row.details
        MERGE (a)-[:HAS_REQUIREMENT]->(r)
        """,
    ),
    (
        "verifications",
        "verifications",
        """
        UNWIND $rows AS row
        MATCH (r:Requirement {id: row.requirementId})
        MATCH (p:Project {id: row.projectId})
        MERGE (r)-[v:VERIFIED_BY]->(p)
        SET v.method = row.method
        """,
    ),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="directory of cleaned CSVs")
    parser.add_argument("--reset", action="store_true", help="delete existing graph nodes (incl. legacy project_adr_map) first")
    parser.add_argument("--dry-run", action="store_true", help="parse the CSVs and print counts without touching Neo4j")
    args = parser.parse_args()

    def warn(message):
        print(f"warning: {message}", file=sys.stderr)

    map_path = args.data / MAP_FILE
    if not map_path.exists():
        raise SystemExit(f"Missing {map_path}")

    projects, departments, adr_links, map_adrs = parse_project_map(map_path, warn)
    requirements, verifications, file_adrs = parse_requirements(args.data, warn)

    for code in sorted(set(map_adrs) - set(file_adrs)):
        warn(f"{code} is referenced in {MAP_FILE} but has no requirements file")
    known_projects = {project["id"] for project in projects}
    for project_id in sorted({v["projectId"] for v in verifications} - known_projects):
        warn(f"Project {project_id} appears in an ADR file but not in {MAP_FILE}")

    adrs = [{"code": code, "number": number} for code, number in sorted({**map_adrs, **file_adrs}.items())]
    batches = {
        "projects": projects,
        "departments": departments,
        "adrs": adrs,
        "adr_links": adr_links,
        "requirements": requirements,
        "verifications": verifications,
    }

    if args.dry_run:
        for label, key, _ in LOAD_QUERIES:
            print(f"{label}: {len(batches[key])}")
        return

    from neo4j import GraphDatabase

    load_env(REPO / ".env")
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    try:
        with driver.session(database=os.environ.get("NEO4J_DATABASE") or None) as session:
            if args.reset:
                for label in GRAPH_LABELS:
                    session.run(f"MATCH (n:`{label}`) DETACH DELETE n").consume()
            for statement in schema_statements(SCHEMA_FILE):
                session.run(statement).consume()
            for label, key, query in LOAD_QUERIES:
                session.execute_write(lambda tx: tx.run(query, rows=batches[key]).consume())
                print(f"{label}: {len(batches[key])}")
    finally:
        print("Sucessfully loaded into graph database")
        driver.close()


if __name__ == "__main__":
    main()
