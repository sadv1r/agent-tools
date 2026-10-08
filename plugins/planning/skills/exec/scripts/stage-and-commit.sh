#!/bin/bash
# stage files and commit with a message
# usage: stage-and-commit.sh <message> <file1> [file2 ...]

set -e

if [ $# -lt 2 ]; then
    echo "error: usage: stage-and-commit.sh <message> <file1> [file2 ...]" >&2
    exit 1
fi

# an empty path must be rejected here: as a git pathspec it matches everything under
# the current directory, so it would silently commit the whole tree instead of failing
for arg in "${@:2}"; do
    if [ -z "$arg" ]; then
        echo "error: empty file argument" >&2
        exit 1
    fi
done

do_git() {
    local msg="$1"
    shift
    # every name is passed as a :(literal) pathspec, so one holding '*', '?' or
    # '[...]' matches itself rather than something else. the magic prefix is used
    # rather than GIT_LITERAL_PATHSPECS because hooks inherit that variable and it
    # would silently change how their own pathspecs resolve.
    local path listed=()
    for path in "$@"; do
        listed+=(":(literal)$path")
    done
    git add -- "${listed[@]}"
    git commit -m "$msg" -- "${listed[@]}"
    # a path-scoped commit runs hooks against a temporary index, so nothing a
    # pre-commit hook stages reaches the real index — neither a reformatted copy
    # of a listed path nor an unlisted one the hook adds itself, such as a
    # regenerated lockfile. reconcile every path the commit actually recorded,
    # not just the listed ones: an unlisted path would otherwise sit in the index
    # as a staged deletion of a file present in both HEAD and the worktree.
    # anything staged but not committed is left alone.
    # diff-tree reports paths from the repository root while a pathspec resolves
    # against the current directory, so :(top) anchors them; without it the reset
    # silently matches nothing whenever the caller sits in a subdirectory.
    local committed=()
    while IFS= read -r -d '' path; do
        committed+=(":(top,literal)$path")
    done < <(git diff-tree --no-commit-id --name-only -r --root -z HEAD)
    if [ ${#committed[@]} -gt 0 ]; then
        git reset -q -- "${committed[@]}"
    fi
}

do_git "$@"
