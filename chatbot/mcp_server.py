"""Read-only MCP tools for the SRP8 ADR compliance graph."""

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from chatbot import graph

mcp = MCPServer("adr-graph", instructions="Read-only access to the SRP8 ADR compliance graph.")


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except graph.QueryRejected as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def find_projects(search: str) -> dict:
    """Find projects by name or ID. search is a project name like 'Headlights'
    or an ID like 'SRP8-012' (also 'SRP8-12'). Matching ignores case and extra
    spaces. Returns IDs, names and departments. Use this before any tool that
    needs a project_id."""
    result = _call(graph.find_projects, search)
    if result is None or result["count"] == 0:
        raise ToolError(
            f"No project matches {search!r}. Use a project name or an ID like 'SRP8-012'."
        )
    return result


@mcp.tool()
def get_project_compliance(project_id: str) -> dict:
    """ADRs a project must comply with, and how many requirements are assigned
    to it under each ADR, with verification methods. Also lists requirements
    filed under an ADR that is missing from the project's ADR list.
    project_id looks like 'SRP8-012'; call find_projects first if you only have a name."""
    result = _call(graph.project_compliance, project_id)
    if result is None:
        raise ToolError(f"No project {project_id!r}. Try find_projects.")
    return result


@mcp.tool()
def get_adr_overview(adr: str) -> dict:
    """One ADR: its name, how many requirements it has, and which projects and
    departments must comply with it. adr can be 'ADR-13', 'adr 13' or '13'."""
    result = _call(graph.adr_overview, adr)
    if result is None:
        raise ToolError(f"No ADR matches {adr!r}. Use a code like 'ADR-13' or '13'.")
    return result


@mcp.tool()
def list_requirements(
    adr: str,
    project_id: str = "",
    verification_method: str = "",
    limit: int = 20,
) -> dict:
    """List requirements for one ADR. Each item has the ADR code, clause, short
    title, shortened text, and who verifies it and how. Optional project_id
    (like 'SRP8-012') keeps only that project's rows. Optional verification_method
    matches any method containing that word, ignoring case, so 'inspection' also
    matches 'Inspection/Test'. 'N/A' means marked as not needing verification."""
    result = _call(graph.list_requirements, adr, project_id, verification_method, limit)
    if result is None:
        raise ToolError(f"No ADR matches {adr!r}. Use a code like 'ADR-13' or '13'.")
    return result


@mcp.tool()
def get_clause(adr: str, clause: str) -> dict:
    """Full text of one clause and its sub-clauses, plus who verifies each and how.
    For example clause '8.1' also returns 8.1.1 and 8.1.2. adr can be 'ADR-13' or '13'."""
    result = _call(graph.get_clause, adr, clause)
    if result is None:
        raise ToolError(f"No ADR matches {adr!r}, or the clause is missing. Use a code like 'ADR-13'.")
    if result["total"] == 0:
        raise ToolError(f"No clause {clause!r} on {result['adr']}.")
    return result


@mcp.tool()
def search_requirements(text: str, adr: str = "", limit: int = 10) -> dict:
    """Keyword search across requirement titles and text. Optional adr limits
    the search to one ADR ('ADR-13' or '13'). Returns ADR code, clause, title
    and a shortened excerpt."""
    result = _call(graph.search_requirements, text, adr, limit)
    return result


@mcp.tool()
def find_gaps(project_id: str = "", department: str = "") -> dict:
    """Compliance gaps. Reports requirements with no verification method yet
    (a method of 'N/A' is a decision, not a gap), requirements filed under an
    ADR missing from that project's ADR list, and projects with no ADRs.
    Optional project_id and department narrow the report. department is a name
    like 'Embedded Systems'."""
    result = _call(graph.find_gaps, project_id, department)
    if result is None:
        raise ToolError(f"No project {project_id!r}. Try find_projects.")
    return result


@mcp.tool()
def run_read_only_cypher(query: str) -> dict:
    """Last resort for a question the other tools cannot answer. Runs one
    read-only Cypher query. Write queries, LOAD CSV, apoc.load and PROFILE are
    refused. Results are capped at 50 rows. Prefer the other tools."""
    return _call(graph.read_only_cypher, query)


@mcp.resource(
    "adr://overview",
    name="overview",
    description="Every project ID and name, every ADR code and name, and every department.",
    mime_type="text/plain",
)
def overview() -> str:
    return graph.overview()


if __name__ == "__main__":
    mcp.run()
