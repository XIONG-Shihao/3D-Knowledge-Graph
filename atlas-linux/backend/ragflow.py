from urllib.parse import quote

import httpx


class RAGFlowError(Exception):
    pass


class RAGFlowClient:
    """Python adapter to the documented HTTP API; no browser-visible credentials."""

    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    def request(self, method, path, **kwargs):
        try:
            with httpx.Client(
                base_url=self.settings.ragflow_url.rstrip("/") + "/api/v1/",
                headers={"Authorization": "Bearer " + self.settings.ragflow_key},
                timeout=self.settings.timeout,
                transport=self.transport,
            ) as client:
                response = client.request(method, path.lstrip("/"), **kwargs)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404 and "graph" in path:
                raise RAGFlowError(
                    "This RAGFlow release does not expose the legacy graph API. "
                    "Build a Graph artifact in RAGFlow and import its JSON here."
                ) from exc
            raise RAGFlowError(
                f"RAGFlow returned HTTP {exc.response.status_code}. Check server configuration."
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RAGFlowError(
                "Could not reach RAGFlow or read its response. Check the server URL and connection."
            ) from exc
        if not isinstance(body, dict) or body.get("code") != 0:
            message = (
                str(body.get("message", "Invalid response"))
                if isinstance(body, dict)
                else "Invalid response"
            )
            raise RAGFlowError("RAGFlow: " + message[:500])
        return body.get("data")

    def create_dataset(self, name, description):
        body = {
            "name": name,
            "description": description,
            "permission": "me",
            "chunk_method": "naive",
        }
        if self.settings.embedding_model:
            body["embedding_model"] = self.settings.embedding_model
        data = self.request("POST", "datasets", json=body)
        if not isinstance(data, dict) or not data.get("id"):
            raise RAGFlowError("RAGFlow did not return a dataset ID.")
        return data["id"]

    def dataset(self, dataset_id):
        data = self.request("GET", "datasets", params={"id": dataset_id, "page_size": 1})
        if not isinstance(data, list) or not data or data[0].get("id") != dataset_id:
            raise RAGFlowError("Dataset not found or not accessible with this API key.")
        return data[0]

    def path(self, dataset_id):
        return "datasets/" + quote(dataset_id, safe="")

    def upload(self, dataset_id, name, blob):
        data = self.request(
            "POST", self.path(dataset_id) + "/documents", files={"file": (name, blob)}
        )
        if not isinstance(data, list) or not data or not data[0].get("id"):
            raise RAGFlowError("RAGFlow did not return an uploaded document ID.")
        return data[0]["id"]

    def parse(self, dataset_id, remote_id):
        self.request("POST", self.path(dataset_id) + "/chunks", json={"document_ids": [remote_id]})

    def documents(self, dataset_id):
        return self.paginate(self.path(dataset_id) + "/documents", "docs")

    def chunks(self, dataset_id, remote_id):
        return self.paginate(
            self.path(dataset_id) + "/documents/" + quote(remote_id, safe="") + "/chunks", "chunks"
        )

    def paginate(self, path, key):
        items = []
        for page in range(1, 101):
            data = self.request("GET", path, params={"page": page, "page_size": 100})
            batch = data if isinstance(data, list) else (data or {}).get(key)
            if not isinstance(batch, list):
                raise RAGFlowError("Unexpected RAGFlow pagination response.")
            items.extend(batch)
            total = data.get("total") if isinstance(data, dict) else None
            if len(batch) < 100 or (total is not None and len(items) >= total):
                return items
        raise RAGFlowError("Result exceeds 10,000 items. Reduce dataset size for this MVP.")

    def retrieve(self, dataset_id, question):
        data = self.request(
            "POST",
            "retrieval",
            json={
                "question": question,
                "dataset_ids": [dataset_id],
                "page": 1,
                "page_size": 12,
                "similarity_threshold": 0.2,
                "highlight": False,
            },
        )
        return (data or {}).get("chunks", [])

    def delete_document(self, dataset_id, remote_id):
        self.request("DELETE", self.path(dataset_id) + "/documents", json={"ids": [remote_id]})

    def graph(self, dataset_id):
        return self.request("GET", self.path(dataset_id) + "/knowledge_graph")

    def build_graph(self, dataset_id):
        return self.request("POST", self.path(dataset_id) + "/run_graphrag")

    def graph_status(self, dataset_id):
        return self.request("GET", self.path(dataset_id) + "/trace_graphrag")
