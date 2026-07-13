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


@dataclasses.dataclass(frozen=True)
class SearchPage:
    final_url: str
    next_page_url: str | None
    results: list[SearchResult]


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


def search_url(query: str, package_type: str, sort: str, page: int) -> str:
    parameters: dict[str, str | int] = {
        "name": query,
        "type": package_type,
        "sort": sort,
    }
    if page > 1:
        parameters["page"] = page
    return f"{ORIGIN}/packages?{urllib.parse.urlencode(parameters)}"


def search_packages(query: str, package_type: str, sort: str, page: int) -> SearchPage:
    response = fetch(search_url(query, package_type, sort, page))
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
            )
        )
    next_page = next(
        (
            link
            for link in document.select("nav[aria-label='Package pages'] a")
            if compact_text(link.get_text()) == "Next →"
        ),
        None,
    )
    return SearchPage(
        final_url=str(response.url),
        next_page_url=urllib.parse.urljoin(ORIGIN, str(next_page["href"]))
        if next_page
        else None,
        results=results,
    )


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
        readme=readme.get_text("\n", strip=True) if include_readme and readme else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    search_parser = commands.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--type", default="")
    search_parser.add_argument("--sort", default="downloads")
    search_parser.add_argument("--page", type=int, default=1)

    show_parser = commands.add_parser("show")
    show_parser.add_argument("package_name")
    show_parser.add_argument("--readme", action="store_true")

    arguments = parser.parse_args()
    if arguments.command == "search" and arguments.page < 1:
        parser.error("--page must be at least 1")
    if arguments.command == "search":
        output = dataclasses.asdict(
            search_packages(arguments.query, arguments.type, arguments.sort, arguments.page)
        )
    else:
        output = dataclasses.asdict(package_details(arguments.package_name, arguments.readme))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
