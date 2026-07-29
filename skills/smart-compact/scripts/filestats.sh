#!/usr/bin/env zsh

SCRIPT_NAME=${0:t}

main() {
    if (( $# == 0 )); then
        print -u2 "usage: $SCRIPT_NAME <path> [path ...]"
        return 2
    fi

    export LC_NUMERIC=en_US.UTF-8
    grouped() { printf "%'d" $1 }

    local p rel size bytes lines words tokens sortkey
    local -a rows=()

    for p in "$@"; do
        rel=${${p:a}#$PWD/}

        if [[ ! -e $p ]]; then
            rows+=("-2\t0\t0\t0\t$rel\tDoes not exist")
            continue
        fi

        if [[ -d $p ]]; then
            rows+=("-2\t0\t0\t0\t$rel\tDirectory, not a file")
            continue
        fi

        size=$(du -h "$p" | awk '{print $1}')
        bytes=$(stat -f%z "$p")
        lines=$(wc -l < "$p" | tr -d ' ')
        words=$(wc -w < "$p" | tr -d ' ')
        if LC_ALL=C grep -qI . "$p"; then
            tokens=$(ttok < "$p")
            sortkey=$tokens
            tokens=$(grouped $tokens)
        else
            tokens="<binary>"
            sortkey=-1
        fi

        rows+=("$sortkey\t$words\t$lines\t$bytes\t$rel\t$size\t$(grouped $lines)\t$(grouped $words)\t$tokens")
    done

    print "path\tsize\tlines\twords\ttokens"
    print -l -- $rows \
        | sort -t$'\t' -k1,1nr -k2,2nr -k3,3nr -k4,4nr \
        | cut -f5-
}

main "$@"
