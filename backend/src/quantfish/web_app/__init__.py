from quantfish.web_app.settings import WebSettings

__all__ = ["WebSettings", "create_app"]


def create_app(*args, **kwargs):
    from quantfish.web_app.app import create_app as _create_app

    return _create_app(*args, **kwargs)
