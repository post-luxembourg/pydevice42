# Install dependencies

```shell
poetry install
```

# IPython setup

## Credentials

Setup credentials using [direnv](https://direnv.net/):

```shell
cp .envrc.sample .envrc
vim .envrc
direnv allow
```

## Hack

With direnv:

```shell
poetry run ipython -i hacking.ipy
```

Without direnv:

```shell
source .envrc
poetry run ipython -i hacking.ipy
```
