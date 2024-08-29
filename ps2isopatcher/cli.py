from pathlib import Path
import os

import click

from ps2isopatcher.iso import (
    Ps2Iso, TreeFolder, walk_tree
)

def print_tree(root: TreeFolder):
    for _, _, files in walk_tree(root):
        for f in files:
            print(f.path)

@click.group()
def cli():
    pass

iso_opt = click.argument(
    "iso",
    type=click.Path(),
)

@cli.command()
@iso_opt
def tree(iso):
    iso = Ps2Iso(iso, mutable=False)
    print_tree(iso.tree)

@cli.command()
@iso_opt
@click.option(
    "-o", "--output-path",
    default=None,
    type=click.Path(),
)
@click.option(
    "-r", "--replace",
    nargs=2,
    type=click.Tuple([str, click.Path()]),
    multiple=True,
)
@click.option(
    "--move/--no-move",
    default=True
)
def patch(iso, output_path, replace, move):
    _iso = Ps2Iso(iso, mutable=True)
    iso = Path(iso)
    if output_path is None:
        output_path = Path(os.getcwd()) / f"{iso.stem}_patched.iso"
    replacements = []
    for iso_path, path in replace:
        with open(path, "rb") as f:
            replacements.append((iso_path, f.read()))
    _iso.replace_files(replacements, allow_move=move)
    _iso.write(str(output_path))


if __name__ == "__main__":
    cli()