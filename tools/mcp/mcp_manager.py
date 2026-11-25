import asyncio
from multiprocessing.dummy import connection
from typing import Any

from config.config import Config
from tools.mcp import client
from tools.mcp.client import MCPClient, MCPServerStatus
from tools.mcp.mcp_tool import MCPTool
from tools.registry import ToolRegistry


class MCPManager:
    def __init__(self,config:Config):
        self.config=config
        self._clients:dict[str,MCPClient]={}

        self._initialized=False

    async def initialize(self)-> None:
        if self._initialized:
            return

        mcp_configs=self.config.mcp_servers

        if not mcp_configs:
            return

        for name,server_config in mcp_configs.items():
            if not server_config.enabled:
                continue
            self._clients[name]=MCPClient(
                name=name,
                config=server_config,
                cwd=self.config.cwd
            )
        connection_tasks=[
            asyncio.wait_for(client.connect(),timeout=client.config.startup_timeout_sec) for name,client in self._clients.items()
            ]
        await asyncio.gather(*connection_tasks,return_exceptions=True)
        self._initialized=True
    def register_tools(self,registry:ToolRegistry)->int:
        count=0
        for name,client in self._clients.items():
            if client.status != MCPServerStatus.CONNECTED:
                continue
            for tool_info in client._tools.values():
                mcp_tool=MCPTool(
                    config=self.config,
                    tool_info=tool_info,
                    client=client,
                    name=f'{client.name}__{tool_info.name}'
                )
                registry.register_mcp_tool(mcp_tool)
                count+=1
        return count
    async def shutdown(self)->None:
        disconnection_tasks=[client.disconnect() for client in self._clients.values()]
        await asyncio.gather(*disconnection_tasks,return_exceptions=True)
        self._clients.clear()
        self._initialized=False
    def get_all_servers(self)->list[dict[str,Any]]:
        servers=[]
        for name,client in self._clients.items():
            server_info={
                'name':name,
                'status':client.status.value,
                'tools':len(client.tools)
            }
            servers.append(server_info)
        return servers
