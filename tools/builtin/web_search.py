"""go deeper into this later"""

import re

from pydantic import BaseModel, Field
from ddgs import DDGS

from tools.base import Tool, ToolInvocation, ToolKind, ToolResult



class WebSearchParams(BaseModel):
    query:str=Field(
        ...,description='Search query'
    )
    max_results:int=Field(
        10,ge=1,le=100,
        description='Maximum results to return(default:10)'
        )

class WebSearchTool(Tool):
    name='web_search'
    description=(
        'Search the web for information.Returns search results with titles ,URLs and snippets'
        
        )

    kind=ToolKind.NETWORK
    schema=WebSearchParams

    async def execute(self,invocation:ToolInvocation)->ToolResult:
        params=WebSearchParams(**invocation.params)

        try:
            results=DDGS().text(
                #try to get this information from the LLM
                params.query,
                region='us-en',
                safesearch="off",
                timelimit="off",
                page=1,
                backend="auto",
                )
        except Exception as e:
            return ToolResult.error_result(f'Search failed:{e}')
        if not results:
            return ToolResult.success_result(
                f'No results found for:{params.query}',
                metadata={
                    "results":len(results),
                }
            )
        output_lines=[f'Search results for:{params.query}']

        for i,result in enumerate(results,start=1):
            output_lines.append(
                f"{i}.Title:{result['title']}")
            output_lines.append(
                f"  URL:{result['href']}")
            if result.get('body'):
                output_lines.append(
                    f"   Snippet:{result['body']}")
            output_lines.append("")
        return ToolResult.success_result(
            "\n".join(output_lines),
            metadata={
                "results":len(results),
            },
        )