from app import create_app
from models import db

app = create_app()


@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database initialized.")


@app.cli.command("seed")
def seed():
    print("Seed command placeholder.")
