from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .intent import DOCUMENT_TASK, classify_intent
from .models import SearchResult


SearchTool = Callable[[str, int], tuple[list[SearchResult], list[dict[str, Any]]]]


def needs_agent_harness(question: str) -> bool:
    """Keep simple factual questions on the evaluated low-overhead RAG path."""
    return classify_intent(question).intent == DOCUMENT_TASK


@dataclass
class AgentResult:
    answer: str
    results: list[SearchResult]
    traces: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


class DocumentAgentHarness:
    """Bounded tool-calling loop for indirect and multi-step document requests."""

    def __init__(self, provider: Any, *, max_steps: int = 3) -> None:
        self.provider = provider
        self.max_steps = max_steps

    def run(
        self,
        question: str,
        history: Sequence[dict[str, str]],
        documents: Sequence[dict[str, object]],
        search: SearchTool,
        memories: Sequence[dict[str, object]] = (),
    ) -> AgentResult:
        input_items: list[Any] = [dict(message) for message in history[-8:]]
        input_items.append({"role": "user", "content": question})
        tools = self._tools()
        all_results: list[SearchResult] = []
        traces: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        response = None

        for _ in range(self.max_steps):
            response = self.provider.client.responses.create(
                model=self.provider.chat_model,
                instructions=self._instructions(documents, memories),
                input=input_items,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
            )
            calls = [
                item for item in response.output if getattr(item, "type", None) == "function_call"
            ]
            if not calls:
                text = getattr(response, "output_text", None)
                if not text:
                    raise RuntimeError("The document agent returned no answer.")
                return AgentResult(text.strip(), self._unique(all_results), traces, tool_calls)

            input_items.extend(self._dump_item(item) for item in response.output)
            for call in calls:
                arguments = json.loads(getattr(call, "arguments", "{}") or "{}")
                name = str(getattr(call, "name", ""))
                if name == "list_documents":
                    output: object = {"documents": list(documents)}
                elif name == "search_documents":
                    query = str(arguments.get("query", "")).strip()
                    top_k = max(1, min(int(arguments.get("top_k", 5)), 8))
                    results, search_traces = search(query, top_k)
                    all_results.extend(results)
                    traces.extend(search_traces)
                    output = {
                        "query": query,
                        "results": [self._tool_result(item) for item in results],
                    }
                else:
                    output = {"error": f"Unknown tool: {name}"}
                tool_calls.append({"name": name, "arguments": arguments})
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": str(getattr(call, "call_id")),
                        "output": json.dumps(output, ensure_ascii=False),
                    }
                )

        if response is not None and getattr(response, "output_text", None):
            return AgentResult(
                response.output_text.strip(), self._unique(all_results), traces, tool_calls
            )
        raise RuntimeError("The document agent exceeded its tool-call limit without answering.")

    @staticmethod
    def _instructions(
        documents: Sequence[dict[str, object]],
        memories: Sequence[dict[str, object]],
    ) -> str:
        names = ", ".join(str(item["name"]) for item in documents) or "none"
        memory_text = "\n".join(
            f"- [{item.get('category', 'memory')}] {item.get('content', '')}"
            for item in memories
        ) or "(none)"
        return (
            "You are a conversational document agent. The documents attached to this "
            f"conversation are: {names}. Use search_documents whenever the request depends "
            "on document content. You may search more than once with focused queries for "
            "recommendations, comparisons, summaries, or learning plans. Do not invent what "
            "a document contains. Cite document facts using the exact labels returned by the "
            "tool. You may make useful recommendations by reasoning from retrieved evidence, "
            "but clearly present them as your recommendation rather than a quotation from the "
            "document. If essential user context is missing, ask one concise clarifying "
            "question. If evidence is missing, say so plainly. Keep spoken-friendly answers "
            "under 160 words unless the user explicitly asks for detail, and never expose "
            "internal chain-of-thought. Personalize with the user-approved long-term memory "
            "below when relevant. It is background, not document evidence, and the current "
            f"request overrides it if they conflict.\n--- USER MEMORY ---\n{memory_text}\n"
            "--- END USER MEMORY ---"
        )

    @staticmethod
    def _tools() -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "name": "list_documents",
                "description": "List documents attached to the current conversation.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "search_documents",
                "description": (
                    "Search the documents attached to this conversation. Returns grounded "
                    "excerpts with exact citation labels."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A focused standalone search query.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of evidence chunks, from 1 to 8.",
                        },
                    },
                    "required": ["query", "top_k"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        ]

    @staticmethod
    def _dump_item(item: Any) -> object:
        if hasattr(item, "model_dump"):
            return item.model_dump(exclude_none=True)
        return item

    @staticmethod
    def _tool_result(item: SearchResult) -> dict[str, object]:
        return {
            "citation": (
                f"[Document {item.chunk.document_name}, PDF page {item.chunk.pdf_page}]"
            ),
            "chunk_id": item.chunk.chunk_id,
            "text": item.chunk.text,
        }

    @staticmethod
    def _unique(results: Sequence[SearchResult]) -> list[SearchResult]:
        selected: list[SearchResult] = []
        seen: set[str] = set()
        for result in results:
            if result.chunk.chunk_id not in seen:
                seen.add(result.chunk.chunk_id)
                selected.append(result)
        return selected[:16]
