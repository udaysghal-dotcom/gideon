"""Read-only queries against the SRP8 ADR graph.

The connection reads .env itself, so the process that starts this module does not
need Neo4j settings in its environment.
"""

import os
import re
from pathlib import Path

from neo4j import READ_ACCESS, GraphDatabase, unit_of_work

REPO = Path(__file__).resolve().parent.parent

DETAIL_LIMIT = 240
LIST_LIMIT = 50
SEARCH_LIMIT = 25
CLAUSE_LIMIT = 40
GAP_EXAMPLES = 15
PROJECT_LIMIT = 20
CYPHER_ROW_LIMIT = 50
CYPHER_TIMEOUT = 10

PROJECT_ID_PATTERN = re.compile(r"SRP8-0*(\d{1,3})", re.IGNORECASE)
ADR_PATTERN = re.compile(r"(?:ADR[-\s]*)?0*(\d+)", re.IGNORECASE)
FORBIDDEN_CYPHER = re.compile(r"\b(?:load\s+csv|apoc\.load|profile)\b", re.IGNORECASE)
_driver = None


class QueryRejected(Exception):
    """A custom Cypher query was refused or failed."""


def load_env(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def clean(value):
    return " ".join(str(value or "").split())


def project_id(value):
    """'SRP8-12' and 'srp8-012' both become 'SRP8-012'. Anything else is returned trimmed."""
    text = clean(value)
    match = PROJECT_ID_PATTERN.fullmatch(text)
    if match:
        return f"SRP8-{int(match.group(1)):03d}"
    return text


def adr_code(value):
    """'ADR-13', 'adr 13' and '13' all become 'ADR-13'. Returns '' when it is not an ADR code."""
    text = clean(value)
    match = ADR_PATTERN.fullmatch(text)
    if not match:
        return ""
    return f"ADR-{int(match.group(1)):02d}"


def shorten(value, limit=DETAIL_LIMIT):
    text = clean(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def clamp(value, default, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(number, maximum))


def clause_sort_key(clause):
    key = []
    for part in (clause or "").split("."):
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return key


def jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return str(value)


def driver():
    global _driver
    if _driver is None:
        load_env(REPO / ".env")
        missing = [key for key in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD") if not os.environ.get(key)]
        if missing:
            raise RuntimeError(f"Missing Neo4j setting(s) in .env: {', '.join(missing)}")
        _driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        )
    return _driver


def database():
    return os.environ.get("NEO4J_DATABASE") or None


def read(statement, **params):
    def work(tx):
        return [record.data() for record in tx.run(statement, **params)]

    with driver().session(database=database(), default_access_mode=READ_ACCESS) as session:
        return session.execute_read(work)


def _departments(links):
    departments = [link for link in links or [] if link.get("name")]
    return sorted(departments, key=lambda link: (link.get("role") != "primary", link["name"]))


def find_projects(search):
    """Case-insensitive match on a project name, or an exact project ID."""
    text = clean(search)
    if not text:
        return None
    as_id = project_id(text)
    by_id = PROJECT_ID_PATTERN.fullmatch(text) is not None
    rows = read(
        """
        MATCH (p:Project)
        WHERE ($by_id AND p.id = $id) OR (NOT $by_id AND toLower(p.name) CONTAINS toLower($name))
        OPTIONAL MATCH (p)-[rel:IN_DEPARTMENT]->(d:Department)
        RETURN p.id AS id, p.name AS name,
               [dept IN collect({name: d.name, role: rel.role}) WHERE dept.name IS NOT NULL] AS departments
        ORDER BY p.name
        """,
        by_id=by_id,
        id=as_id,
        name=text,
    )
    projects = [
        {"id": row["id"], "name": row["name"], "departments": _departments(row["departments"])}
        for row in rows
    ]
    return {
        "query": text,
        "count": len(projects),
        "truncated": len(projects) > PROJECT_LIMIT,
        "projects": projects[:PROJECT_LIMIT],
    }


def project_compliance(project_id_value):
    pid = project_id(project_id_value)
    rows = read(
        """
        MATCH (p:Project {id: $id})
        OPTIONAL MATCH (p)-[rel:IN_DEPARTMENT]->(d:Department)
        RETURN p.id AS id, p.name AS name,
               [dept IN collect({name: d.name, role: rel.role}) WHERE dept.name IS NOT NULL] AS departments
        """,
        id=pid,
    )
    if not rows:
        return None
    project = rows[0]

    adrs = read(
        """
        MATCH (p:Project {id: $id})-[rel:MUST_COMPLY_WITH]->(a:ADR)
        OPTIONAL MATCH (a)-[:HAS_REQUIREMENT]->(r:Requirement)-[v:VERIFIED_BY]->(p)
        WITH a, rel, count(r) AS requirements,
             [method IN collect(DISTINCT v.method) WHERE method IS NOT NULL] AS methods,
             sum(CASE WHEN r IS NOT NULL AND v.method IS NULL THEN 1 ELSE 0 END) AS unset
        RETURN a.code AS code, a.name AS name, rel.rank AS rank,
               requirements, methods, unset
        ORDER BY rel.rank
        """,
        id=pid,
    )
    extra = read(
        """
        MATCH (p:Project {id: $id})<-[:VERIFIED_BY]-(:Requirement)<-[:HAS_REQUIREMENT]-(a:ADR)
        WHERE NOT (p)-[:MUST_COMPLY_WITH]->(a)
        RETURN a.code AS code, a.name AS name, count(*) AS requirements
        ORDER BY a.code
        """,
        id=pid,
    )
    return {
        "id": project["id"],
        "name": project["name"],
        "departments": _departments(project["departments"]),
        "adrs": [
            {
                "code": row["code"],
                "name": row["name"],
                "rank": row["rank"],
                "requirements": row["requirements"],
                "verification_methods": sorted(row["methods"]),
                "unset_methods": row["unset"],
            }
            for row in adrs
        ],
        "adrs_not_on_list": extra,
    }


def adr_overview(adr):
    code = adr_code(adr)
    if not code:
        return None
    rows = read(
        """
        MATCH (a:ADR {code: $code})
        OPTIONAL MATCH (a)-[:HAS_REQUIREMENT]->(r:Requirement)
        WITH a, count(r) AS requirements
        OPTIONAL MATCH (p:Project)-[:MUST_COMPLY_WITH]->(a)
        OPTIONAL MATCH (p)-[:IN_DEPARTMENT]->(d:Department)
        RETURN a.code AS code, a.number AS number, a.name AS name, requirements,
               collect(DISTINCT {id: p.id, name: p.name}) AS projects,
               collect(DISTINCT d.name) AS departments
        """,
        code=code,
    )
    if not rows:
        return None
    row = rows[0]
    projects = sorted((item for item in row["projects"] if item.get("id")), key=lambda item: item["id"])
    departments = sorted(name for name in row["departments"] if name)
    return {
        "code": row["code"],
        "number": row["number"],
        "name": row["name"],
        "requirements": row["requirements"],
        "projects": projects,
        "departments": departments,
    }


def _requirement_rows(code, project, method):
    return read(
        """
        MATCH (a:ADR {code: $code})-[:HAS_REQUIREMENT]->(r:Requirement)
        OPTIONAL MATCH (r)-[v:VERIFIED_BY]->(p:Project)
        WITH r, [link IN collect({
            project_id: p.id, project_name: p.name, method: v.method
        }) WHERE link.project_id IS NOT NULL] AS links
        WHERE ($project = '' OR any(link IN links WHERE link.project_id = $project))
          AND ($method = '' OR any(link IN links WHERE link.method IS NOT NULL
               AND toLower(link.method) CONTAINS toLower($method)))
        RETURN r.adr AS adr, r.clause AS clause, r.name AS name, r.details AS details, links
        """,
        code=code,
        project=project,
        method=method,
    )


def list_requirements(adr, project_id_value="", verification_method="", limit=20):
    code = adr_code(adr)
    if not code:
        return None
    if not read("MATCH (a:ADR {code: $code}) RETURN a.code AS code", code=code):
        return None
    project = project_id(project_id_value) if clean(project_id_value) else ""
    method = clean(verification_method)
    rows = _requirement_rows(code, project, method)
    rows.sort(key=lambda row: (clause_sort_key(row["clause"]), row["name"] or ""))
    shown = rows[: clamp(limit, 20, LIST_LIMIT)]
    return {
        "adr": code,
        "project_id": project,
        "verification_method": method,
        "total": len(rows),
        "shown": len(shown),
        "truncated": len(shown) < len(rows),
        "requirements": [_requirement(row, full_text=False, project=project, method=method) for row in shown],
    }


def get_clause(adr, clause):
    code = adr_code(adr)
    clause = clean(clause)
    if not code or not clause:
        return None
    if not read("MATCH (a:ADR {code: $code}) RETURN a.code AS code", code=code):
        return None
    rows = read(
        """
        MATCH (a:ADR {code: $code})-[:HAS_REQUIREMENT]->(r:Requirement)
        WHERE r.clause = $clause OR r.clause STARTS WITH $clause + '.'
        OPTIONAL MATCH (r)-[v:VERIFIED_BY]->(p:Project)
        WITH r, [link IN collect({
            project_id: p.id, project_name: p.name, method: v.method
        }) WHERE link.project_id IS NOT NULL] AS links
        RETURN r.adr AS adr, r.clause AS clause, r.name AS name, r.details AS details, links
        """,
        code=code,
        clause=clause,
    )
    rows.sort(key=lambda row: (clause_sort_key(row["clause"]), row["name"] or ""))
    shown = rows[:CLAUSE_LIMIT]
    return {
        "adr": code,
        "clause": clause,
        "total": len(rows),
        "shown": len(shown),
        "truncated": len(shown) < len(rows),
        "requirements": [_requirement(row, full_text=True) for row in shown],
    }


def _requirement(row, full_text, project="", method=""):
    details = row["details"] or ""
    links = row["links"]
    if project:
        links = [link for link in links if link["project_id"] == project]
    if method:
        links = [link for link in links if link["method"] and method.lower() in link["method"].lower()]
    return {
        "adr": row["adr"],
        "clause": row["clause"],
        "name": row["name"] or "",
        "details": details if full_text else shorten(details),
        "verifications": sorted(links, key=lambda link: link["project_id"]),
    }


def search_requirements(text, adr="", limit=10):
    query = _lucene(text)
    if not query:
        raise QueryRejected("Search text is empty.")
    code = adr_code(adr) if clean(adr) else ""
    if clean(adr) and not code:
        raise QueryRejected(f"{clean(adr)!r} is not an ADR code. Use a code like 'ADR-13' or '13'.")
    rows = read(
        """
        CALL db.index.fulltext.queryNodes('requirement_text', $q) YIELD node, score
        WHERE $code = '' OR node.adr = $code
        RETURN node.adr AS adr, node.clause AS clause, node.name AS name,
               node.details AS details, score
        ORDER BY score DESC
        LIMIT $limit
        """,
        q=query,
        code=code,
        limit=clamp(limit, 10, SEARCH_LIMIT),
    )
    return {
        "query": clean(text),
        "adr": code,
        "count": len(rows),
        "requirements": [
            {
                "adr": row["adr"],
                "clause": row["clause"],
                "name": row["name"] or "",
                "details": shorten(row["details"]),
                "score": round(row["score"], 2),
            }
            for row in rows
        ],
    }


def _lucene(text):
    words = []
    for word in clean(text).split():
        words.append(re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r"\\\1", word))
    return " ".join(words)


def find_gaps(project_id_value="", department=""):
    project = project_id(project_id_value) if clean(project_id_value) else ""
    department = clean(department)
    if project and not read("MATCH (p:Project {id: $id}) RETURN p.id AS id", id=project):
        return None
    if department:
        names = read(
            "MATCH (d:Department) WHERE toLower(d.name) = toLower($name) RETURN d.name AS name",
            name=department,
        )
        if not names:
            raise QueryRejected(f"No department named {department!r}.")
        department = names[0]["name"]

    missing = read(
        """
        MATCH (r:Requirement)-[v:VERIFIED_BY]->(p:Project)
        WHERE v.method IS NULL
          AND ($project = '' OR p.id = $project)
          AND ($department = '' OR EXISTS {
              MATCH (p)-[:IN_DEPARTMENT]->(d:Department) WHERE d.name = $department
          })
        RETURN r.adr AS adr, r.clause AS clause, r.name AS name,
               p.id AS project_id, p.name AS project_name
        ORDER BY r.adr, r.clause, p.id
        """,
        project=project,
        department=department,
    )
    mismatches = read(
        """
        MATCH (p:Project)<-[:VERIFIED_BY]-(:Requirement)<-[:HAS_REQUIREMENT]-(a:ADR)
        WHERE NOT (p)-[:MUST_COMPLY_WITH]->(a)
          AND ($project = '' OR p.id = $project)
          AND ($department = '' OR EXISTS {
              MATCH (p)-[:IN_DEPARTMENT]->(d:Department) WHERE d.name = $department
          })
        RETURN p.id AS project_id, p.name AS project_name,
               a.code AS adr, a.name AS adr_name, count(*) AS requirements
        ORDER BY p.id, a.code
        """,
        project=project,
        department=department,
    )
    without = read(
        """
        MATCH (p:Project)
        WHERE NOT (p)-[:MUST_COMPLY_WITH]->(:ADR)
          AND ($project = '' OR p.id = $project)
          AND ($department = '' OR EXISTS {
              MATCH (p)-[:IN_DEPARTMENT]->(d:Department) WHERE d.name = $department
          })
        RETURN p.id AS id, p.name AS name
        ORDER BY p.id
        """,
        project=project,
        department=department,
    )
    return {
        "project_id": project,
        "department": department,
        "missing_verification_methods": {
            "count": len(missing),
            "examples": missing[:GAP_EXAMPLES],
            "truncated": len(missing) > GAP_EXAMPLES,
        },
        "adr_mismatches": {
            "count": len(mismatches),
            "examples": mismatches,
        },
        "projects_without_adrs": {
            "count": len(without),
            "projects": without,
        },
    }


def read_only_cypher(query):
    statement = clean_query(query)
    if FORBIDDEN_CYPHER.search(statement):
        raise QueryRejected("That query is blocked. LOAD CSV, apoc.load and PROFILE are not allowed.")

    @unit_of_work(timeout=CYPHER_TIMEOUT)
    def check(tx):
        return tx.run("EXPLAIN " + statement).consume().query_type

    try:
        query_type = _execute(check)
    except QueryRejected:
        raise
    except Exception as exc:
        raise QueryRejected(f"Neo4j rejected that query: {_error_text(exc)}") from exc
    if query_type != "r":
        raise QueryRejected("Only read-only queries are allowed.")

    @unit_of_work(timeout=CYPHER_TIMEOUT)
    def run(tx):
        result = tx.run(statement)
        rows = []
        truncated = False
        for record in result:
            if len(rows) == CYPHER_ROW_LIMIT:
                truncated = True
                break
            rows.append(jsonable(record.data()))
        result.consume()
        return rows, truncated

    try:
        rows, truncated = _execute(run)
    except Exception as exc:
        raise QueryRejected(f"Query failed: {_error_text(exc)}") from exc
    return {"rows": rows, "count": len(rows), "truncated": truncated}


def clean_query(query):
    statement = str(query or "").strip()
    if statement.endswith(";"):
        statement = statement[:-1].strip()
    if not statement:
        raise QueryRejected("Query is empty.")
    if ";" in statement:
        raise QueryRejected("Only one statement is allowed.")
    return statement


def _execute(work):
    with driver().session(database=database(), default_access_mode=READ_ACCESS) as session:
        return session.execute_read(work)


def _error_text(exc):
    text = " ".join(str(exc).split())
    return text[:500]


def overview():
    projects = read(
        """
        MATCH (p:Project)
        RETURN p.id AS id, p.name AS name
        ORDER BY p.id
        """
    )
    adrs = read(
        """
        MATCH (a:ADR)
        RETURN a.code AS code, a.name AS name
        ORDER BY a.number
        """
    )
    departments = read(
        """
        MATCH (d:Department)
        RETURN d.name AS name
        ORDER BY d.name
        """
    )
    lines = [f"Projects ({len(projects)}):"]
    lines.extend(f"{row['id']} {row['name']}" for row in projects)
    lines.append("")
    lines.append(f"ADRs ({len(adrs)}):")
    lines.extend(f"{row['code']} {row['name']}" for row in adrs)
    lines.append("")
    lines.append(f"Departments ({len(departments)}):")
    lines.extend(row["name"] for row in departments)
    return "\n".join(lines)
