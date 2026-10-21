# AndroidBuilder / romforge

Android ROM build and device-tree discovery tools, with an offline-first Ubuntu Touch readiness assessment.

## Ubuntu Touch readiness check

```bash
python3 romforge.py ut-check \
  --manufacturer Sony --model "Xperia R1" --ram-gb 2 \
  --json-out reports/xperia-r1.json \
  --markdown-out reports/xperia-r1.md
```

The checker does not require a connected phone. User-provided facts are marked as candidates, unknown properties remain unknown, and no report claims that a port builds or boots. See [device readiness](docs/device-readiness.md), [porting notes](docs/ubuntu-touch-porting.md), and the [repository audit](docs/repository-audit.md).

## Existing ROM builder

Run `python3 romforge.py --help` for CLI usage. The interactive menu requires `questionary`; see `requirements.txt` for dependencies and external build tools.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
