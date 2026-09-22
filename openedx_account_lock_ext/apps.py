"""Open edX LMS and CMS plugin registration."""

from django.apps import AppConfig


class AccountLockConfig(AppConfig):
    """Discoverable application without tables or migrations."""

    name = "openedx_account_lock_ext"
    verbose_name = "Managed account restrictions"
    default_auto_field = "django.db.models.BigAutoField"
    plugin_app = {
        "settings_config": {
            project: {"common": {"relative_path": "settings.common"}} for project in ("lms.djangoapp", "cms.djangoapp")
        },
        "url_config": {
            "lms.djangoapp": {
                "namespace": "account_lock",
                "regex": "^api/account-lock/v1/",
                "relative_path": "urls",
            },
        },
    }

    def ready(self):
        """Register configuration checks and the credential write safeguard."""
        from . import checks  # pylint: disable=unused-import
        from .credentials import connect

        connect()
