"""Shared fixtures and configuration for OmniGuard backend tests."""

import os
import sys
import tempfile
import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from models import db as _db


@pytest.fixture(scope="session")
def app():
    """Create a Flask application instance configured for testing."""
    test_app = create_app()

    # Override config for testing
    test_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "LOG_LEVEL": "CRITICAL",
    })

    # Establish application context
    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.drop_all()


@pytest.fixture(scope="session")
def client(app):
    """A test client for the Flask application."""
    return app.test_client()


@pytest.fixture(scope="session")
def runner(app):
    """A test CLI runner for the Flask application."""
    return app.test_cli_runner()


@pytest.fixture(scope="function")
def db_session(app):
    """Provide a transactional database session scoped to a single test."""
    with app.app_context():
        _db.create_all()
        yield _db.session
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture(scope="module")
def temp_dir():
    """Provide a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory(prefix="omniguard_test_") as tmp:
        yield tmp


@pytest.fixture
def auth_headers(client):
    """Return headers with a valid JWT token for authenticated requests."""
    from flask_jwt_extended import create_access_token

    with client.application.app_context():
        token = create_access_token(identity="test_user")
    return {"Authorization": f"Bearer {token}"}
