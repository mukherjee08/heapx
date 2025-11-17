## Testing Development

1. *Create a new virtual environment* using the command:
  `python -m venve .<env-name>`

2. *Activate the created environment* using the command:
  `source .<env-name>/bin/activate`

3. *Ensure the necessary tooling is installed* using the command:
  `python -m pip install --upgrade pip build twine`

4. **Ensure the repository is clean**. The folder structure should match the below:
```bash
  (iheap) margiela@margiela heapx % tree
  .
  ├── LICENSE
  ├── MANIFEST.in
  ├── pyproject.toml
  ├── README.md
  ├── setup.py
  ├── src
  │   └── heapx
  │       ├── __init__.py
  │       └── heapx.c
  └── USAGE_GUIDE.md

  3 directories, 8 files
```

5. *Build the sdist and wheel distributions* using the command:
  `python -m build --sdist --wheel`

6. *Check the generated sdist and wheel distribution builds* using the below command:
  `python -m twine check dist/*`

