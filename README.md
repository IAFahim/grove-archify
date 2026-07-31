# vex-ee-3 architecture docs

Submodule target for `vex-ee-3/_docs`. **Hub only at root** — topic folders hold the maps.

## Live

https://iafahim.github.io/grove-archify/

## Layout

```
index.html          # hub (no maps)
README.md
grove/              # how BovineLabs Grove works
  index.html
  src/*.json
  *.html            # Archify maps
nerve-client/       # Daggertooth client go-in-game (separate topic)
  index.html
  src/*.json
  *.html
```

## Rules

1. Never dump numbered map HTML at repo root.
2. One topic = one folder with its own `index.html`.
3. JSON IR lives in that topic’s `src/`.

## Regenerate a map

```bash
git clone --depth 1 https://github.com/tt-a1i/archify.git /tmp/archify
ARCH=/tmp/archify/archify/bin/archify.mjs

node $ARCH deliver architecture grove/src/01-toy-machine.architecture.json \
  grove/01-toy-machine.architecture.html --quality standard
```

## Parent project

```bash
# in vex-ee-3
git submodule update --init --recursive
# open _docs/index.html or the Pages URL
```
