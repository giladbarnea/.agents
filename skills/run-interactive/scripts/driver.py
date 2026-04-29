#!/usr/bin/env python3
"""
Interactive process driver for LLM agents.

Runs an interactive CLI process via PTY and exposes a file-based interface
for reading output and sending input.

Usage:
    python driver.py <session_id> <command> [args...]

Creates:
    /tmp/interactive_<session_id>.log    - Output log (read this)
    /tmp/interactive_<session_id>.in     - Input file (write here)

Log format:
    [START] <command>        - Process started
    [PID] <pid>              - Process ID
    [OUT] <text>             - Process output line
    [AWAIT]                  - Process is waiting for input
    [SENT] <text>            - Input sent to process
    [EXIT:<code>]            - Process exited
"""
import pty
import os
import sys
import select
import time
import subprocess


def get_process_state(pid: int) -> str:
    """Get process state (S=sleeping, R=running, etc.)"""
    try:
        result = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True, text=True, timeout=1
        )
        return result.stdout.strip()[:1]
    except Exception:
        return "?"


def is_blocked_on_stdin_linux(pid: int) -> bool:
    """Linux: check /proc/<pid>/syscall for read(0, ...)"""
    try:
        with open(f"/proc/{pid}/syscall", "r") as f:
            parts = f.read().strip().split()
            if len(parts) >= 2:
                syscall_nr = int(parts[0])
                fd_arg = int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1])
                return syscall_nr in (0, 63) and fd_arg == 0
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return False


class InteractiveDriver:
    def __init__(self, session_id: str, command: list[str], heuristic_delay: float = 0.15):
        self.session_id = session_id
        self.command = command
        self.log_file = f"/tmp/interactive_{session_id}.log"
        self.input_file = f"/tmp/interactive_{session_id}.in"
        self.heuristic_delay = heuristic_delay

        self.last_output_time: float | None = None
        self.had_output = False
        self.await_logged = False
        self.is_linux = sys.platform.startswith("linux")

    def log(self, tag: str, text: str = ""):
        """Append to output log."""
        with open(self.log_file, "a") as f:
            if text:
                f.write(f"[{tag}] {text}\n")
            else:
                f.write(f"[{tag}]\n")
            f.flush()

    def check_input_file(self) -> str | None:
        """Check if input file exists. Returns content and deletes file."""
        if os.path.exists(self.input_file):
            try:
                with open(self.input_file, "r") as f:
                    content = f.read()
                os.remove(self.input_file)
                if content.endswith("\n"):
                    content = content[:-1]
                return content
            except (IOError, OSError):
                pass
        return None

    def notify_output(self):
        """Called when output received."""
        self.last_output_time = time.monotonic()
        self.had_output = True
        self.await_logged = False

    def is_waiting_for_input(self, pid: int) -> bool:
        """Detect if process is waiting for input."""
        if self.is_linux:
            return is_blocked_on_stdin_linux(pid)

        # macOS/other: heuristic
        if not self.had_output or self.last_output_time is None:
            return False
        elapsed = time.monotonic() - self.last_output_time
        if elapsed < self.heuristic_delay:
            return False
        return get_process_state(pid) == "S"

    def run(self):
        # Clean up stale files
        for f in [self.log_file, self.input_file]:
            if os.path.exists(f):
                os.remove(f)

        open(self.log_file, "w").close()
        self.log("START", " ".join(self.command))

        master_fd, slave_fd = pty.openpty()
        pid = os.fork()

        if pid == 0:
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(slave_fd)
            try:
                os.execvp(self.command[0], self.command)
            except Exception as e:
                print(f"exec failed: {e}", file=sys.stderr)
                os._exit(1)

        os.close(slave_fd)
        self.log("PID", str(pid))

        output_buffer = ""

        while True:
            ready, _, _ = select.select([master_fd], [], [], 0.05)

            if ready:
                try:
                    data = os.read(master_fd, 4096).decode(errors="replace")
                    if data:
                        output_buffer += data
                        while "\n" in output_buffer:
                            line, output_buffer = output_buffer.split("\n", 1)
                            self.log("OUT", line)
                        if output_buffer:
                            self.log("OUT", output_buffer)
                            output_buffer = ""
                        self.notify_output()
                except OSError:
                    break

            if self.is_waiting_for_input(pid) and not self.await_logged:
                self.log("AWAIT")
                self.await_logged = True

            llm_input = self.check_input_file()
            if llm_input is not None:
                self.log("SENT", llm_input)
                os.write(master_fd, (llm_input + "\n").encode())
                self.notify_output()

            result = os.waitpid(pid, os.WNOHANG)
            if result[0] != 0:
                exit_code = os.WEXITSTATUS(result[1]) if os.WIFEXITED(result[1]) else -1
                time.sleep(0.1)
                try:
                    while True:
                        r, _, _ = select.select([master_fd], [], [], 0.05)
                        if not r:
                            break
                        data = os.read(master_fd, 4096).decode(errors="replace")
                        if not data:
                            break
                        for line in data.split("\n"):
                            if line:
                                self.log("OUT", line)
                except OSError:
                    pass
                self.log(f"EXIT:{exit_code}")
                break

        os.close(master_fd)


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <session_id> <command> [args...]", file=sys.stderr)
        sys.exit(1)

    session_id = sys.argv[1]
    command = sys.argv[2:]

    driver = InteractiveDriver(session_id, command)
    driver.run()


if __name__ == "__main__":
    main()
