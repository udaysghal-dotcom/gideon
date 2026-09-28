"""Known-answer checks for the read-only ADR tools. Re-run after any data reload."""

import asyncio
import json

from mcp import Client

from chatbot.mcp_server import mcp

HEADLIGHTS = "SRP8-012"
HEADLIGHT_ADRS = {"ADR-06", "ADR-13", "ADR-46", "ADR-76", "ADR-92"}


def call(name, arguments=None):
    async def run():
        async with Client(mcp) as client:
            return await client.call_tool(name, arguments or {})

    return asyncio.run(run())


def data(name, arguments=None):
    result = call(name, arguments)
    assert not result.is_error, result.content[0].text if result.content else result
    return json.loads(result.content[0].text)


def error(name, arguments=None):
    result = call(name, arguments)
    assert result.is_error
    return result.content[0].text


def test_find_projects_by_name_and_id():
    by_name = data("find_projects", {"search": "  Headlights  "})
    assert by_name["count"] == 1
    project = by_name["projects"][0]
    assert project["id"] == HEADLIGHTS
    assert project["name"] == "Headlights"
    assert {item["name"] for item in project["departments"]} == {"Embedded Systems", "Chassis & Bodywork"}

    by_id = data("find_projects", {"search": "srp8-12"})
    assert [item["id"] for item in by_id["projects"]] == [HEADLIGHTS]

    message = error("find_projects", {"search": "no-such-project"})
    assert "No project matches" in message


def test_headlights_compliance():
    result = data("get_project_compliance", {"project_id": HEADLIGHTS})
    assert result["name"] == "Headlights"
    assert {item["code"] for item in result["adrs"]} == HEADLIGHT_ADRS
    assert all(item["requirements"] > 0 for item in result["adrs"])
    assert result["adrs_not_on_list"] == []

    message = error("get_project_compliance", {"project_id": "SRP8-999"})
    assert "No project" in message


def test_adr_overview():
    result = data("get_adr_overview", {"adr": "adr 13"})
    assert result["code"] == "ADR-13"
    assert result["name"].startswith("Installation of Lighting")
    assert result["requirements"] == 359
    assert any(item["id"] == HEADLIGHTS for item in result["projects"])

    seatbelts = data("get_adr_overview", {"adr": "4"})
    assert seatbelts["code"] == "ADR-04"
    assert seatbelts["name"] == "Seatbelts"

    message = error("get_adr_overview", {"adr": "ADR-99"})
    assert "No ADR" in message


def test_list_requirements_method_filter():
    result = data(
        "list_requirements",
        {"adr": "13", "verification_method": "inspection", "limit": 5},
    )
    assert result["adr"] == "ADR-13"
    assert result["total"] > result["shown"] == 5
    for requirement in result["requirements"]:
        assert requirement["adr"] == "ADR-13"
        assert requirement["clause"]
        methods = [link["method"] or "" for link in requirement["verifications"]]
        assert any("inspection" in method.lower() for method in methods)


def test_get_clause_includes_subclauses():
    result = data("get_clause", {"adr": "ADR-13", "clause": "8.1"})
    clauses = {item["clause"] for item in result["requirements"]}
    assert "8.1.4" in clauses
    assert any(clause.startswith("8.1.") for clause in clauses)
    clause = next(item for item in result["requirements"] if item["clause"] == "8.1.4")
    assert "maximum height" in clause["details"]
    projects = {link["project_id"] for link in clause["verifications"]}
    assert {"SRP8-011", "SRP8-012", "SRP8-013", "SRP8-077", "SRP8-171"} <= projects
    assert all(link["method"] == "Inspection" for link in clause["verifications"])

    message = error("get_clause", {"adr": "ADR-13", "clause": "99.99"})
    assert "No clause" in message


def test_search_requirements():
    result = data("search_requirements", {"text": "seatbelt", "limit": 5})
    assert result["count"] >= 1
    assert all(item["adr"] and item["clause"] for item in result["requirements"])

    limited = data("search_requirements", {"text": "lamp", "adr": "46", "limit": 5})
    assert limited["count"] >= 1
    assert {item["adr"] for item in limited["requirements"]} == {"ADR-46"}


def test_find_gaps():
    result = data("find_gaps")
    assert result["missing_verification_methods"]["count"] == 387
    assert result["projects_without_adrs"]["count"] == 36
    mismatches = result["adr_mismatches"]["examples"]
    assert any(item["project_id"] == "SRP8-022" and item["adr"] == "ADR-42" for item in mismatches)

    one = data("find_gaps", {"project_id": "SRP8-022"})
    assert any(item["adr"] == "ADR-42" for item in one["adr_mismatches"]["examples"])
    assert one["projects_without_adrs"]["count"] == 0

    message = error("find_gaps", {"department": "Not a department"})
    assert "No department" in message


def test_read_only_cypher():
    result = data("run_read_only_cypher", {"query": "MATCH (a:ADR {code: 'ADR-04'}) RETURN a.name AS name"})
    assert result["rows"] == [{"name": "Seatbelts"}]
    assert result["truncated"] is False

    write = error("run_read_only_cypher", {"query": "CREATE (n:Nope {name: 'x'})"})
    assert "read-only" in write

    blocked = error("run_read_only_cypher", {"query": "LOAD CSV FROM 'file:///tmp/x.csv' AS row RETURN row"})
    assert "blocked" in blocked


def test_overview_resource():
    async def run():
        async with Client(mcp) as client:
            return await client.read_resource("adr://overview")

    result = asyncio.run(run())
    text = result.contents[0].text
    assert "SRP8-012 Headlights" in text
    assert "ADR-04 Seatbelts" in text
    assert "Embedded Systems" in text
    assert "Departments (" in text
