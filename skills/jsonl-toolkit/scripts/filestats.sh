#!/usr/bin/env bash

script_name=${0##*/}

grouped() {
    printf "%'d" "$1"
}

usage() {
    printf 'usage: %s <path> [path ...]\n' "$script_name"
    printf 'Print file sizes and estimated text token counts.\n'
}

main() {
    if (( $# == 0 )); then
        usage >&2
        return 2
    fi
    if (( $# == 1 )) && [[ $1 == -h || $1 == --help ]]; then
        usage
        return 0
    fi
    if [[ $1 == -* ]]; then
        printf '%s: unknown option: %s\n' "$script_name" "$1" >&2
        usage >&2
        return 2
    fi

    export LC_NUMERIC=en_US.UTF-8

    local path relative_path size bytes lines words tokens sort_key absolute_path tab
    local -a rows=()
    tab=$'\t'

    for path in "$@"; do
        if [[ $path == /* ]]; then
            absolute_path=$path
        else
            absolute_path=$PWD/$path
        fi
        relative_path=${absolute_path#$PWD/}

        if [[ ! -e $path ]]; then
            rows+=("-2${tab}0${tab}0${tab}0${tab}${relative_path}${tab}Does not exist")
            continue
        fi

        if [[ -d $path ]]; then
            rows+=("-2${tab}0${tab}0${tab}0${tab}${relative_path}${tab}Directory, not a file")
            continue
        fi

        size=$(du -h "$path" | awk '{print $1}')
        bytes=$(stat -f%z "$path")
        lines=$(wc -l < "$path" | tr -d ' ')
        words=$(wc -w < "$path" | tr -d ' ')
        if LC_ALL=C grep -qI . "$path"; then
            tokens=$(ttok < "$path")
            sort_key=$tokens
            tokens=$(grouped "$tokens")
        else
            tokens='<binary>'
            sort_key=-1
        fi

        rows+=("${sort_key}${tab}${words}${tab}${lines}${tab}${bytes}${tab}${relative_path}${tab}${size}${tab}$(grouped "$lines")${tab}$(grouped "$words")${tab}${tokens}")
    done

    printf 'path\tsize\tlines\twords\ttokens\n'
    printf '%s\n' "${rows[@]}" \
        | sort -t$'\t' -k1,1nr -k2,2nr -k3,3nr -k4,4nr \
        | cut -f5-
}

main "$@"
