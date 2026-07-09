import click

from app import create_app
from app.extensions import db


@click.group()
def cli():
    pass


@cli.command("init-db")
def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()
    click.echo("database initialized")


if __name__ == "__main__":
    cli()
