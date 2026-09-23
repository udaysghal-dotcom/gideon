// Graph schema for the SRP8 project / ADR compliance data.
//
// Nodes
//   (:Project     {id, name})                         one per row of project_adr_map_clean.csv
//   (:Department  {name})                             primary/secondary departments
//   (:ADR         {code, number})                     one per ADR referenced or with an adr_XX.csv
//   (:Requirement {id, adr, checklist, clause, name, details})
//
// Relationships
//   (:Project)-[:IN_DEPARTMENT {role: 'primary' | 'secondary'}]->(:Department)
//   (:Project)-[:MUST_COMPLY_WITH {rank, ranks}]->(:ADR)
//   (:ADR)-[:HAS_REQUIREMENT]->(:Requirement)
//   (:Requirement)-[:VERIFIED_BY {method}]->(:Project)
//
// Requirement.id is "<ADR code>|<checklist>|<clause>|<req name>" so the same
// requirement repeated across rows (one per project) maps to a single node.

CREATE CONSTRAINT project_id IF NOT EXISTS
FOR (p:Project) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT department_name IF NOT EXISTS
FOR (d:Department) REQUIRE d.name IS UNIQUE;

CREATE CONSTRAINT adr_code IF NOT EXISTS
FOR (a:ADR) REQUIRE a.code IS UNIQUE;

CREATE CONSTRAINT requirement_id IF NOT EXISTS
FOR (r:Requirement) REQUIRE r.id IS UNIQUE;

CREATE INDEX project_name IF NOT EXISTS
FOR (p:Project) ON (p.name);

CREATE INDEX adr_number IF NOT EXISTS
FOR (a:ADR) ON (a.number);

CREATE INDEX requirement_adr_clause IF NOT EXISTS
FOR (r:Requirement) ON (r.adr, r.clause);

CREATE INDEX verified_by_method IF NOT EXISTS
FOR ()-[v:VERIFIED_BY]-() ON (v.method);
