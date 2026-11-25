import asyncio
import os
import re
import signal
import fnmatch

from pathlib import Path
import sys

from pydantic import BaseModel,Field

from tools.base import Tool, ToolConfirmation, ToolInvocation, ToolKind, ToolResult

BLOCKED_COMMANDS={
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "mkfs",
    "fdisk",
    "parted",
    ":(){ :|:& };:",
    "chmod 777 /",
    "chmod -R 777",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
    "sudo reboot",
    "shutdown /s /f",
    "kill -9",
    "chown",
    "chmod",
    "passwd",
    "mount",
    "umount",
    "ifconfig",
    "ip",
    "iptables",
    "ping -c 1000",
    "netstat -anl | grep LISTEN",
    "ss -anl | grep LISTEN",
    "tcpdump",
    "traceroute",
    "dig +short myip.opendns.com @resolver1.opendns.com",
    "wget --no-check-certificate",
    "curl -k",
    "ssh -i /path/to/key",
    "scp -P 2222 user@host:/path/to/file",
    "rsync -avz /source/dir/ user@host:/destination/dir/",
    "sudo apt-get update && sudo apt-get upgrade"
}

_SEGMENT_SEPARATORS=re.compile(r"&&|\|\||[;|\n]")
_WRAPPER_TOKENS={"sudo","doas","env","nohup","time","command","exec"}


def find_blocked_command(command:str)->str | None:
    """Return the blocked pattern that matches, or None.

    Single-token patterns only match at a command position (the start of the
    command or of a segment after &&, ||, ;, | or a newline). That stops
    ordinary words such as "pip", "zip", "skip" or "description" from being
    rejected because of the short "ip" pattern. Multi-token patterns are
    matched anywhere but must respect word boundaries.
    """
    normalized=command.lower().strip()
    if not normalized:
        return None

    segments=[]
    for raw in _SEGMENT_SEPARATORS.split(normalized):
        tokens=raw.strip().split()
        while tokens and tokens[0] in _WRAPPER_TOKENS:
            tokens.pop(0)
        if tokens:
            segments.append(" ".join(tokens))

    for blocked in BLOCKED_COMMANDS:
        if " " in blocked or any(ch in blocked for ch in "|&;/:~"):
            pattern=r"(?<![a-z0-9])" + re.escape(blocked) + r"(?![a-z0-9])"
            if re.search(pattern,normalized):
                return blocked
            continue
        for segment in segments:
            if segment==blocked:
                return blocked
            if segment.startswith(blocked) and not segment[len(blocked)].isalnum():
                return blocked
    return None


class ShellParams(BaseModel):
    command:str=Field(...,description='The shell command to execute')
    timeout:int=Field(120,ge=1,le=1000,description='Timeout in second(default is 120)')
    cwd:str | None=Field(None,description='Working directory for the command')


class ShellTool(Tool):
    name='shell'
    kind=ToolKind.SHELL
    description="Execute a shell command.Use this for running system commands,scripts and CLI tools. "
    schema=ShellParams

    async def get_confirmation(
            self,
            invocation:ToolInvocation
            )->ToolConfirmation | None:
        params=ShellParams(**invocation.params)

        blocked=find_blocked_command(params.command)
        if blocked:
            return ToolConfirmation(
                tool_name=self.name,
                params=invocation.params,
                description=f"Execute(BLOCKED:{blocked}):{params.command}",
                command=params.command,
                is_dangerous= True
    
            )
                        
    
        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.params,
            description=f"Execute:{params.command}",
            command=params.command,
            is_dangerous=False

        )
        

    async def execute(self, invocation:ToolInvocation)->ToolResult:
        params=ShellParams(**invocation.params)
        blocked=find_blocked_command(params.command)
        if blocked:
            return ToolResult.error_result(
                f'Command blocked for safety:{params.command}',
                metadata={'blocked':True,'pattern':blocked}
            )
        if params.cwd:
            cwd=Path(params.cwd)
            if not cwd.is_absolute():
                cwd=invocation.cwd/cwd
        else:
            cwd=invocation.cwd

        if not cwd.exists():
            return ToolResult.error_result(f"Working directory doesn't exist:{cwd}")
        env=self._build_environment()
        if sys.platform=='win32':
            shell_cmd=["cmd.exe","/c",params.command]
        else:
            shell_cmd=["/bin/bash","-c",params.command]
        process= await asyncio.create_subprocess_exec(
            *shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
        try:
            stdout_data,stderr_data=await asyncio.wait_for(
            process.communicate(),
            timeout=params.timeout,)
        except asyncio.TimeoutError:
            if sys.platform !='win32':
                os.killpg(os.getpgid(process.pid),signal.SIGKILL)
            else:
                killer=await asyncio.create_subprocess_exec(
                    "taskkill","/F","/T","/PID",str(process.pid),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await killer.wait()
            await process.wait()
            return ToolResult.error_result(
                f'Command timed out after {params.timeout}'
            )
        stdout=stdout_data.decode('utf-8',errors='replace')
        stderr=stderr_data.decode('utf-8',errors='replace')
        exit_code=process.returncode

        output=""
        if stdout.strip():
            output +=stdout.rstrip()
        if stderr.strip():
            output +='\n --- stderr ---'
            output +=stderr.rstrip()
        if exit_code !=0:
            output +=f'\n Exit code:{exit_code}'
        if len(output)>100 *1024:
            output=output[:100*1024] + "\n...[output truncated]"
        return ToolResult(
            success=exit_code==0,
            output=output,
            error=stderr if exit_code != 0 else None,
            exit_code=exit_code,
        )

    def _build_environment(self) -> dict[str,str]:
        env=os.environ.copy()

        shell_environment=self.config.shell_environment

        if not shell_environment.ignore_default_excludes:
            for pattern in shell_environment.exclude_patterns:
                keys_to_remove= [k for k in env.keys() if fnmatch.fnmatch(k.upper(),pattern.upper())]

                for k in keys_to_remove:
                    del env[k]

        if shell_environment.set_vars:
            env.update(shell_environment.set_vars)

        return env

        




