"""All Neo4j calls live here (the only place with Cypher).

(:Entity {id, key, name, type, document_id, owner_id})
(:Entity)-[:RELATES {type, chunk_id, confidence}]->(:Entity)
(:Chunk {id, document_id, owner_id, section})-[:MENTIONS]->(:Entity)

Entity ids are "<document_id>:<key>", so each document has its own nodes and
deleting a document never touches another user's graph.
"""

import re

from neo4j import Driver, GraphDatabase

from adaptive_rag.config import settings
from adaptive_rag.schemas import GraphExtraction, GraphPath


class GraphUnavailableError(Exception):
    """Neo4j is not running or not configured."""


class GraphStore:
    """Writes extracted graphs and answers traversal queries, always per owner."""

    def __init__(self, driver: Driver | None = None) -> None:
        if driver is None:
            if not settings.neo4j_password.get_secret_value():
                raise GraphUnavailableError("NEO4J_PASSWORD is not set in .env")
            driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
            )
        self._driver = driver
        self._ensure_schema()

    def close(self) -> None:
        self._driver.close()

    def ping(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def _ensure_schema(self) -> None:
        try:
            with self._driver.session() as session:
                session.run(
                    "CREATE CONSTRAINT entity_id IF NOT EXISTS "
                    "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE"
                )
                session.run(
                    "CREATE INDEX entity_owner IF NOT EXISTS FOR (e:Entity) ON (e.owner_id)"
                )
        except Exception as error:
            raise GraphUnavailableError(f"Cannot reach Neo4j: {error}") from error

    # ------------------------------------------------------------- writing

    def write_document(
        self,
        document_id: str,
        owner_id: str,
        extraction: GraphExtraction,
        chunk_sections: dict[str, str],
    ) -> None:
        """Replace this document's graph with a fresh extraction."""
        entities = [
            {"id": f"{document_id}:{e.key}", "key": e.key, "name": e.name, "type": e.type}
            for e in extraction.entities
        ]
        relations = [
            {
                "source": f"{document_id}:{r.source}",
                "target": f"{document_id}:{r.target}",
                "type": r.relation,
                "chunk_id": r.chunk_id,
                "confidence": r.confidence,
            }
            for r in extraction.relations
        ]
        mentions = [
            {
                "chunk_id": chunk_id,
                "section": chunk_sections.get(chunk_id, ""),
                "entity_id": f"{document_id}:{key}",
            }
            for chunk_id, keys in extraction.mentions.items()
            for key in keys
        ]
        params = {"document_id": document_id, "owner_id": owner_id}
        with self._driver.session() as session:
            session.execute_write(self._delete_tx, document_id)
            session.run(
                """
                UNWIND $entities AS e
                MERGE (n:Entity {id: e.id})
                SET n.key = e.key, n.name = e.name, n.type = e.type,
                    n.document_id = $document_id, n.owner_id = $owner_id
                """,
                entities=entities,
                **params,
            )
            session.run(
                """
                UNWIND $relations AS r
                MATCH (a:Entity {id: r.source}), (b:Entity {id: r.target})
                CREATE (a)-[:RELATES {type: r.type, chunk_id: r.chunk_id,
                                      confidence: r.confidence}]->(b)
                """,
                relations=relations,
            )
            session.run(
                """
                UNWIND $mentions AS m
                MERGE (c:Chunk {id: m.chunk_id})
                SET c.document_id = $document_id, c.owner_id = $owner_id, c.section = m.section
                WITH c, m
                MATCH (e:Entity {id: m.entity_id})
                MERGE (c)-[:MENTIONS]->(e)
                """,
                mentions=mentions,
                **params,
            )

    def delete_document(self, document_id: str) -> None:
        with self._driver.session() as session:
            session.execute_write(self._delete_tx, document_id)

    @staticmethod
    def _delete_tx(tx, document_id: str) -> None:  # type: ignore[no-untyped-def]
        tx.run("MATCH (n) WHERE n.document_id = $id DETACH DELETE n", id=document_id)

    # ------------------------------------------------------------- reading

    def entity_names(self, owner_id: str, document_ids: list[str]) -> list[tuple[str, str]]:
        """(entity id, name) for every entity in the owner's chosen documents."""
        with self._driver.session() as session:
            rows = session.run(
                """
                MATCH (e:Entity)
                WHERE e.owner_id = $owner_id AND e.document_id IN $document_ids
                RETURN e.id AS id, e.name AS name
                """,
                owner_id=owner_id,
                document_ids=document_ids,
            )
            return [(row["id"], row["name"]) for row in rows]

    def link_entities(self, question: str, owner_id: str, document_ids: list[str]) -> list[str]:
        """Entity linking: entities whose name appears in the question (longest first)."""
        text = question.lower()
        found: list[tuple[int, str]] = []
        for entity_id, name in self.entity_names(owner_id, document_ids):
            name_lower = name.lower()
            if re.search(rf"\b{re.escape(name_lower)}\b", text):
                found.append((len(name_lower), entity_id))
        return [entity_id for _, entity_id in sorted(found, reverse=True)]

    def paths_from(
        self, entity_ids: list[str], owner_id: str, document_ids: list[str]
    ) -> list[GraphPath]:
        """Paths up to `graph_max_hops` away from the linked entities, in either direction."""
        if not entity_ids:
            return []
        hops = int(settings.graph_max_hops)  # Cypher cannot take hop counts as parameters
        with self._driver.session() as session:
            rows = session.run(
                f"""
                MATCH p = (start:Entity)-[:RELATES*1..{hops}]-(other:Entity)
                WHERE start.id IN $entity_ids
                  AND all(n IN nodes(p) WHERE n.owner_id = $owner_id
                                          AND n.document_id IN $document_ids)
                RETURN p
                ORDER BY length(p)
                LIMIT $limit
                """,
                entity_ids=entity_ids,
                owner_id=owner_id,
                document_ids=document_ids,
                limit=settings.graph_max_paths,
            )
            return [_to_graph_path(row["p"]) for row in rows]

    def chunks_mentioning(
        self, entity_ids: list[str], owner_id: str, document_ids: list[str]
    ) -> list[str]:
        """IDs of chunks that mention any of these entities, most mentions first."""
        with self._driver.session() as session:
            rows = session.run(
                """
                MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
                WHERE e.id IN $entity_ids AND c.owner_id = $owner_id
                  AND c.document_id IN $document_ids
                RETURN c.id AS id, count(e) AS hits
                ORDER BY hits DESC
                """,
                entity_ids=entity_ids,
                owner_id=owner_id,
                document_ids=document_ids,
            )
            return [row["id"] for row in rows]

    def stats(self, document_id: str) -> dict[str, int]:
        with self._driver.session() as session:
            row = session.run(
                """
                OPTIONAL MATCH (e:Entity {document_id: $id})
                WITH count(e) AS entities
                OPTIONAL MATCH (:Entity {document_id: $id})-[r:RELATES]->()
                RETURN entities, count(r) AS relations
                """,
                id=document_id,
            ).single()
            return {"entities": row["entities"], "relations": row["relations"]}


def _to_graph_path(path) -> GraphPath:  # type: ignore[no-untyped-def]
    """Turn a Neo4j path into names and arrows that keep each edge's real direction."""
    nodes = [node["name"] for node in path.nodes]
    relations = []
    for index, rel in enumerate(path.relationships):
        forward = rel.start_node.element_id == path.nodes[index].element_id
        relations.append(rel["type"] if forward else f"<-{rel['type']}")
    return GraphPath(
        nodes=nodes,
        relations=relations,
        chunk_ids=[rel["chunk_id"] for rel in path.relationships],
    )
