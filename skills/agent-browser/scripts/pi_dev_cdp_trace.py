#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["websocket-client"]
# ///

"""Trace pi.dev's server-rendered package search over raw Chrome DevTools Protocol."""

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field

import websocket


@dataclass
class CDPConnection:
    socket: websocket.WebSocket
    next_identifier: int = 1
    events: list[dict[str, object]] = field(default_factory=list)

    def command(
        self,
        method: str,
        parameters: Mapping[str, object] | None = None,
        session_identifier: str | None = None,
    ) -> dict[str, object]:
        command_identifier = self.next_identifier
        self.next_identifier += 1
        message: dict[str, object] = {
            "id": command_identifier,
            "method": method,
            "params": parameters or {},
        }
        if session_identifier:
            message["sessionId"] = session_identifier
        self.socket.send(json.dumps(message))

        while True:
            response = json.loads(self.socket.recv())
            if response.get("id") != command_identifier:
                self.events.append(response)
                continue
            if "error" in response:
                raise RuntimeError(json.dumps(response["error"]))
            return response.get("result", {})

    def receive(self, timeout_seconds: float) -> dict[str, object] | None:
        self.socket.settimeout(timeout_seconds)
        try:
            response = json.loads(self.socket.recv())
        except websocket.WebSocketTimeoutException:
            return None
        self.events.append(response)
        return response


def browser_websocket_url(port: int) -> str:
    with urllib.request.urlopen(f"http://localhost:{port}/json/version") as response:
        version = json.load(response)
    return str(version["webSocketDebuggerUrl"])


def cdp_connection(port: int) -> CDPConnection:
    socket = websocket.create_connection(
        browser_websocket_url(port), suppress_origin=True
    )
    return CDPConnection(socket)


def package_search_url(query: str, package_type: str, sort: str) -> str:
    parameters = urllib.parse.urlencode(
        {"name": query, "type": package_type, "sort": sort}
    )
    return f"https://pi.dev/packages?{parameters}"


def matching_requests(
    events: list[dict[str, object]], session_identifier: str
) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    request_positions: dict[str, int] = {}

    for event in events:
        if event.get("sessionId") != session_identifier:
            continue
        if event.get("method") != "Network.requestWillBeSent":
            continue
        parameters = event["params"]
        if not isinstance(parameters, dict):
            continue
        request = parameters["request"]
        if not isinstance(request, dict):
            continue
        url = str(request["url"])
        resource_type = str(parameters["type"])
        if not url.startswith("https://pi.dev/"):
            continue
        if resource_type not in {"Document", "Fetch"}:
            continue
        request_identifier = str(parameters["requestId"])
        redirect_response = parameters.get("redirectResponse")
        if isinstance(redirect_response, dict):
            requests[request_positions[request_identifier]]["response"] = {
                "status": redirect_response["status"],
                "location": redirect_response.get("headers", {}).get("location"),
            }
        requests.append(
            {
                "resourceType": resource_type,
                "method": request["method"],
                "url": url,
                "requestHeaders": request.get("headers", {}),
            }
        )
        request_positions[request_identifier] = len(requests) - 1

    for event in events:
        if event.get("sessionId") != session_identifier:
            continue
        if event.get("method") != "Network.responseReceived":
            continue
        parameters = event["params"]
        if not isinstance(parameters, dict):
            continue
        request_identifier = str(parameters["requestId"])
        request_position = request_positions.get(request_identifier)
        if request_position is None:
            continue
        response = parameters["response"]
        if not isinstance(response, dict):
            continue
        requests[request_position]["response"] = {
            "status": response["status"],
            "mimeType": response["mimeType"],
            "location": response.get("headers", {}).get("location"),
        }
    return requests


def package_detail_url(package_name: str) -> str:
    package_path = urllib.parse.quote(package_name, safe="@/")
    return f"https://pi.dev/packages/{package_path}"


def capture_url(port: int, url: str) -> dict[str, object]:
    connection = cdp_connection(port)
    target_identifier = ""
    try:
        target = connection.command(
            "Target.createTarget", {"url": "about:blank", "background": True}
        )
        target_identifier = str(target["targetId"])
        attached = connection.command(
            "Target.attachToTarget", {"targetId": target_identifier, "flatten": True}
        )
        session_identifier = str(attached["sessionId"])
        connection.command("Network.enable", session_identifier=session_identifier)
        connection.command("Page.enable", session_identifier=session_identifier)
        connection.command(
            "Page.navigate", {"url": url}, session_identifier=session_identifier
        )

        deadline = time.monotonic() + 20
        load_event_received_at: float | None = None
        while time.monotonic() < deadline:
            event = connection.receive(0.25)
            if event is None:
                if load_event_received_at and time.monotonic() - load_event_received_at > 0.75:
                    break
                continue
            if event.get("sessionId") != session_identifier:
                continue
            if event.get("method") == "Page.loadEventFired":
                load_event_received_at = time.monotonic()

        return {
            "requestedUrl": url,
            "requests": matching_requests(connection.events, session_identifier),
        }
    finally:
        if target_identifier:
            connection.command("Target.closeTarget", {"targetId": target_identifier})
        connection.socket.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9222)
    commands = parser.add_subparsers(dest="command", required=True)

    search_parser = commands.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--type", default="")
    search_parser.add_argument("--sort", default="downloads")

    show_parser = commands.add_parser("show")
    show_parser.add_argument("package_name")

    arguments = parser.parse_args()
    url = (
        package_search_url(arguments.query, arguments.type, arguments.sort)
        if arguments.command == "search"
        else package_detail_url(arguments.package_name)
    )
    print(json.dumps(capture_url(arguments.port, url), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
