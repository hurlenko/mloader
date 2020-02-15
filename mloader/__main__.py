import click

from mloader import __version__ as about
from mloader.mloader import main

if __name__ == "__main__":
    click.echo(click.style(about.__doc__, fg="blue"))
    main(prog_name="mloader")
