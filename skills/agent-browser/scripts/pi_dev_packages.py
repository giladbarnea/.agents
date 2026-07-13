#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["beautifulsoup4", "httpx"]
# ///

"""Search pi.dev's package catalog and inspect a package's server-rendered README."""

import argparse
import dataclasses
import json
import urllib.parse

import bs4
import httpx


ORIGIN = "https://pi.dev"


@dataclasses.dataclass(frozen=True)
class SearchResult:
    name: str
    description: str
    package_url: str
    downloads: int
    published_at_unix_milliseconds: int
    types: list[str]


@dataclasses.dataclass(frozen=True)
class PackageDetails:
    name: str
    package_url: str
    types: list[str]
    install_command: str
    readme: str | None


def compact_text(value: str) -> str:
    """Collapse whitespace in rendered text.

    >>> compact_text("  Pi     package  ")
    'Pi package'
    """
    return " ".join(value.split())


def fetch(url: str) -> httpx.Response:
    response = httpx.get(url, follow_redirects=True, timeout=20)
    response.raise_for_status()
    return response


def search_url(query: str, package_type: str, sort: str) -> str:
    parameters = urllib.parse.urlencode(
        {"name": query, "type": package_type, "sort": sort}
    )
    return f"{ORIGIN}/packages?{parameters}"


def search_packages(query: str, package_type: str, sort: str) -> tuple[str, list[SearchResult]]:
    response = fetch(search_url(query, package_type, sort))
    document = bs4.BeautifulSoup(response.text, "html.parser")
    results: list[SearchResult] = []

    for card in document.select("article[data-package-card='true']"):
        link = card.select_one("h3.packages-name a")
        description = card.select_one("p.packages-desc")
        if link is None or description is None:
            raise ValueError("pi.dev returned a package card without a name or description")
        results.append(
            SearchResult(
                name=str(card["data-package-name"]),
                description=compact_text(description.get_text()),
                package_url=urllib.parse.urljoin(ORIGIN, str(link["href"]).split("?")[0]),
                downloads=int(str(card["data-package-downloads"])),
                published_at_unix_milliseconds=int(str(card["data-package-date"])),
                types=str(card.get("data-package-types", "")).split(),
            )
        )
    return str(response.url), results


def package_url(package_name: str) -> str:
    package_path = urllib.parse.quote(package_name, safe="@/")
    return f"{ORIGIN}/packages/{package_path}"


def package_details(package_name: str, include_readme: bool) -> PackageDetails:
    response = fetch(package_url(package_name))
    document = bs4.BeautifulSoup(response.text, "html.parser")
    detail = document.select_one("section.packages-detail-card")
    if detail is None:
        raise ValueError(f"pi.dev did not return package details for {package_name!r}")
    install_command = detail.select_one("div.packages-install code")
    if install_command is None:
        raise ValueError(f"pi.dev did not return an install command for {package_name!r}")
    readme = document.select_one("div.packages-readme")
    if include_readme and readme is None:
        raise ValueError(f"pi.dev did not return a README for {package_name!r}")
    return PackageDetails(
        name=package_name,
        package_url=str(response.url),
        types=[badge.get_text(strip=True) for badge in detail.select(".packages-badge")],
        install_command=compact_text(install_command.get_text()).removeprefix("$ "),
        readme=compact_text(readme.get_text(" ")) if include_readme and readme else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    search_parser = commands.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--type", default="")
    search_parser.add_argument("--sort", default="downloads")

    show_parser = commands.add_parser("show")
    show_parser.add_argument("package_name")
    show_parser.add_argument("--readme", action="store_true")

    arguments = parser.parse_args()
    if arguments.command == "search":
        final_url, results = search_packages(arguments.query, arguments.type, arguments.sort)
        output: dict[str, object] = {
            "final_url": final_url,
            "results": [dataclasses.asdict(result) for result in results],
        }
    else:
        output = dataclasses.asdict(package_details(arguments.package_name, arguments.readme))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
