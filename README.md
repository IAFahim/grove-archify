# Grove Archify

Interactive architecture maps for **BovineLabs Grove** (`com.bovinelabs.grove` **2.1.1**).

Goal: learn Grove deep enough to rebuild the pipeline — editor import, bake, blob layout, `GraphImpl` / `GraphExecution`, source-gen dispatch, built-ins, and `GroveState`.

## Live site

After GitHub Pages is enabled on this repo:

**https://iafahim.github.io/grove-archify/**

Local:

```bash
# from repo root
python3 -m http.server 8765
# open http://127.0.0.1:8765/
```

## Maps

| # | File | Type | What you learn |
|---|------|------|----------------|
| 01 | `01-map.architecture.html` | architecture | Whole machine · three assemblies |
| 02 | `02-pipeline.workflow.html` | workflow | Author → import → bake |
| 03 | `03-frame.sequence.html` | sequence | One frame / one entity |
| 04 | `04-blob.dataflow.html` | dataflow | Blob bytes + Type dispatch |
| 05 | `05-codegen.sequence.html` | sequence | Source-gen contract |
| 06 | `06-selector.lifecycle.html` | lifecycle | Selectors + state edges |
| 07 | `07-node.architecture.html` | architecture | Custom node four-piece kit |
| 08 | `08-state.dataflow.html` | dataflow | GroveState memory model |

Start at [`index.html`](index.html).

## Regenerate

```bash
git clone --depth 1 https://github.com/tt-a1i/archify.git /tmp/archify
ARCH=/tmp/archify/archify/bin/archify.mjs

node $ARCH deliver architecture src/01-map.architecture.json 01-map.architecture.html --quality standard
node $ARCH deliver workflow     src/02-pipeline.workflow.json 02-pipeline.workflow.html --quality standard
node $ARCH deliver sequence     src/03-frame.sequence.json     03-frame.sequence.html --quality standard
node $ARCH deliver dataflow     src/04-blob.dataflow.json      04-blob.dataflow.html --quality standard
node $ARCH deliver sequence     src/05-codegen.sequence.json   05-codegen.sequence.html --quality standard
node $ARCH deliver lifecycle    src/06-selector.lifecycle.json 06-selector.lifecycle.html --quality standard
node $ARCH deliver architecture src/07-node.architecture.json  07-node.architecture.html --quality standard
node $ARCH deliver dataflow     src/08-state.dataflow.json     08-state.dataflow.html --quality standard
```

## Used as submodule

In `vex-ee-3`:

```bash
git submodule add https://github.com/IAFahim/grove-archify.git _docs
git submodule update --init --recursive
```

## Source of truth

Diagram facts are traced from package cache:

`Library/PackageCache/com.bovinelabs.grove@c8b04cbdb09c`

## License

Maps and text in this repo: MIT. Grove package itself remains BovineLabs proprietary.
