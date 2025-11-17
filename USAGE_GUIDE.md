## [DEV] Part $1$: Creating the `heapx` module.

1. *Create a new virtual environment* using the command:
  `python -m venv .<env-name>`

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

7. *Ensure that the python version matches the wheel's dist/cpXXX version tag* using the below command:
  `tree && python --version`

8. *Confirm that the python and pip belongs to the created .<env-name>* using the below command:
  `which python && which pip`

---

## [DEV] Part $2$: Install `heapx` development build to venv.

1. *Install the wheel distribution directly* in MacOS using the command:
  `python -m pip install dist/heapx-V.V.V-cpXXX-cpXXX-macosx_12_0_arm64.whl`
  Please note that in the above command $V.V.V$ represents the heapx module version and $XXX$ represents the desired python version.

2. *Install the sdist distribution directly* using the command:
  `python -m pip install dist/heapx-V.V.V.tar.gz`
  Please note that in the above command $V.V.V$ represents the heapx module version.

3. *Install the dource distribution* in the project directory root using the command:
  `python -m pip install -e .`
