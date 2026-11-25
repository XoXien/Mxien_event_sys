"""Explain missing password dependencies before starting the development server."""

from importlib import import_module

from django.core.checks import Tags, Warning, register


@register(Tags.security)
def check_password_estimator(app_configs, **kwargs):
    try:
        import_module("zxcvbn")
    except ModuleNotFoundError as exc:
        if exc.name != "zxcvbn":
            raise
        return [
            Warning(
                "The password strength checker (zxcvbn) is not installed.",
                hint="Run python -m pip install -r requirements.txt in the same "
                "Python environment used to run manage.py.",
                id="accounts.W001",
            )
        ]
    return []
