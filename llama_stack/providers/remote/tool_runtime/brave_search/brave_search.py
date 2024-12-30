# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

from typing import Any, Dict, List

import requests

from llama_stack.apis.tools import Tool, ToolGroupDef, ToolInvocationResult, ToolRuntime
from llama_stack.distribution.request_headers import NeedsRequestProviderData
from llama_stack.providers.datatypes import ToolsProtocolPrivate

from .config import BraveSearchToolConfig


class BraveSearchToolRuntimeImpl(
    ToolsProtocolPrivate, ToolRuntime, NeedsRequestProviderData
):
    def __init__(self, config: BraveSearchToolConfig):
        self.config = config

    async def initialize(self):
        pass

    async def register_tool(self, tool: Tool):
        pass

    async def unregister_tool(self, tool_id: str) -> None:
        return

    def _get_api_key(self) -> str:
        if self.config.api_key:
            return self.config.api_key

        provider_data = self.get_request_provider_data()
        if provider_data is None or not provider_data.api_key:
            raise ValueError(
                'Pass Search provider\'s API Key in the header X-LlamaStack-ProviderData as { "api_key": <your api key>}'
            )
        return provider_data.api_key

    async def discover_tools(self, tool_group: ToolGroupDef) -> List[Tool]:
        raise NotImplementedError("Brave search tool group not supported")

    async def invoke_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> ToolInvocationResult:
        api_key = self._get_api_key()
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "X-Subscription-Token": api_key,
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
        }
        payload = {"q": args["query"]}
        response = requests.get(url=url, params=payload, headers=headers)
        response.raise_for_status()
        results = self._clean_brave_response(response.json())
        content_items = "\n".join([str(result) for result in results])
        return ToolInvocationResult(
            content=content_items,
        )

    def _clean_brave_response(self, search_response):
        clean_response = []
        if "mixed" in search_response:
            mixed_results = search_response["mixed"]
            for m in mixed_results["main"][: self.config.max_results]:
                r_type = m["type"]
                results = search_response[r_type]["results"]
                cleaned = self._clean_result_by_type(r_type, results, m.get("index"))
                clean_response.append(cleaned)

        return clean_response

    def _clean_result_by_type(self, r_type, results, idx=None):
        type_cleaners = {
            "web": (
                ["type", "title", "url", "description", "date", "extra_snippets"],
                lambda x: x[idx],
            ),
            "faq": (["type", "question", "answer", "title", "url"], lambda x: x),
            "infobox": (
                ["type", "title", "url", "description", "long_desc"],
                lambda x: x[idx],
            ),
            "videos": (["type", "url", "title", "description", "date"], lambda x: x),
            "locations": (
                [
                    "type",
                    "title",
                    "url",
                    "description",
                    "coordinates",
                    "postal_address",
                    "contact",
                    "rating",
                    "distance",
                    "zoom_level",
                ],
                lambda x: x,
            ),
            "news": (["type", "title", "url", "description"], lambda x: x),
        }

        if r_type not in type_cleaners:
            return ""

        selected_keys, result_selector = type_cleaners[r_type]
        results = result_selector(results)

        if isinstance(results, list):
            cleaned = [
                {k: v for k, v in item.items() if k in selected_keys}
                for item in results
            ]
        else:
            cleaned = {k: v for k, v in results.items() if k in selected_keys}

        return str(cleaned)
