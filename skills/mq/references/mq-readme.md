# Usage

For more detailed usage and examples, refer to the [documentation](https://mqlang.org/book/).

For a comprehensive collection of practical examples, see the [Example Guide](https://mqlang.org/book/start/example/).
Run `rf https://mqlang.org/book/start/example > /tmp/mq-examples.md` if you need additional examples on top of the examples in this doc.

### Basic usage

Complete list of options (click to show)

```
Usage: mq [OPTIONS] [QUERY OR FILE] [FILES]... [COMMAND]

Commands:
  repl  Start a REPL session for interactive query execution
  help  Print this message or the help of the given subcommand(s)

Arguments:
  [QUERY OR FILE]
  [FILES]...

Options:
  -A, --aggregate
          Aggregate all input files/content into a single array
  -f, --from-file
          load filter from the file
  -I, --input-format <INPUT_FORMAT>
          Set input format [possible values: markdown, mdx, html, text, null, raw]
  -L, --directory <MODULE_DIRECTORIES>
          Search modules from the directory
  -M, --module-names <MODULE_NAMES>
          Load additional modules from specified files
  -m, --import-module-names <IMPORT_MODULE_NAMES>
          Import modules by name, making them available as `name::fn()` in queries
      --args <NAME> <VALUE>
          Sets string that can be referenced at runtime
      --rawfile <NAME> <FILE>
          Sets file contents that can be referenced at runtime
      --stream
          Enable streaming mode for processing large files line by line
  -F, --output-format <OUTPUT_FORMAT>
          Set output format [default: markdown] [possible values: markdown, html, text, json, table, grep, raw, none]
  -U, --update
          Update the input markdown (aliases: -i, --in-place, --inplace)
      --unbuffered
          Unbuffered output
      --list-style <LIST_STYLE>
          Set the list style for markdown output [default: dash] [possible values: dash, plus, star]
      --link-title-style <LINK_TITLE_STYLE>
          Set the link title surround style for markdown output [default: double] [possible values: double, single, paren]
      --link-url-style <LINK_URL_STYLE>
          Set the link URL surround style for markdown links [default: none] [possible values: none, angle]
  -S, --separator <QUERY>
          Specify a query to insert between files as a separator
  -o, --output <FILE>
          Output to the specified file
  -C, --color-output
          Colorize markdown output
  -B, --before-context <NUM>
          Show NUM nodes before each match. Only effective with -F grep
      --after-context <NUM>
          Show NUM nodes after each match. Only effective with -F grep
      --context <NUM>
          Show NUM nodes before and after each match. Only effective with -F grep
      --list
          List all available subcommands (built-in and external)
  -P <PARALLEL_THRESHOLD>
          Number of files to process before switching to parallel processing [default: 10]
  -h, --help
          Print help
  -V, --version
          Print version

# Examples:

## To filter markdown nodes:
mq 'query' file.md

## To read query from file:
mq -f 'file' file.md

## To start a REPL session:
mq repl

# Auto-parsing by file extension:

When no -I flag is given, mq automatically imports the matching module based on the file extension:

.json              import "json" | json::json_parse()
.yaml / .yml       import "yaml" | yaml::yaml_parse()
.toml              import "toml" | toml::toml_parse()
.xml               import "xml"  | xml::xml_parse()
.toon              import "toon" | toon::toon_parse()
.csv               import "csv"  | csv::csv_parse(true)
.tsv               import "csv"  | csv::tsv_parse(true)
.psv               import "csv"  | csv::psv_parse(true)

Use -I raw to disable auto-parsing and receive the raw string.
```

Here's a basic example of how to use `mq`:

```
# Extract all headings from a document
mq '.h' README.md

# Extract only h1 headings
mq '.h(1)' README.md

# Extract h1 and h2 headings
mq '.h(1, 2)' README.md

# Extract headings from level 1 to 3 using a range
mq '.h(1..3)' README.md

# Extract only Rust code blocks
mq '.code("rust")' example.md

# Extract code blocks containing "name"
mq '.code | select(contains("name"))' example.md

# Extract code values from code blocks
mq -A 'pluck(.code.value)' example.md

# Extract language names from code blocks
mq '.code.lang' documentation.md

# Extract URLs from all links
mq '.link.url' README.md

# Filter table cells containing "name"
mq '.[][] | select(contains("name"))' data.md

# Select lists or headers containing "name"
mq 'select(.[] || .h) | select(contains("name"))' docs.md

# Exclude JavaScript code blocks
mq '.code | select(.code.lang != "js")' examples.md

# Convert CSV to markdown table
mq 'include "csv" | csv_parse(true) | csv_to_markdown_table()' example.csv

# Extract a section by title
mq -A 'section::section("Installation")' README.md

# Filter sections by heading level (scalar or range)
mq -A 'section::sections() | section::by_level(2)' README.md
mq -A 'section::sections() | section::by_level(1..2)' README.md
```

### Composing Workflows with Subcommands

`mq` subcommands are designed to work together via Unix pipes.

```
# Convert Excel report to Markdown, then extract all headings
mq conv report.xlsx | mq '.h'

# Convert a Word document and extract a specific section
mq conv document.docx | mq -A 'section::section("Summary")'

# Convert and view Markdown directly in the terminal
mq conv slides.pdf | mq view
```

Run `mq --list` to see all available subcommands (built-in and external).

