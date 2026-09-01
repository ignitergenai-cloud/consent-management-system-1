"""Jinja2 template engine for rendering notification templates."""

import structlog
from jinja2 import Environment, PackageLoader, select_autoescape

logger = structlog.get_logger(__name__)


class TemplateEngine:
    """Renders notification templates using Jinja2.

    Loads templates from the notification_service/templates package directory
    and provides methods for rendering SMS, HTML email, and plain text email
    templates with variable substitution.
    """

    def __init__(self) -> None:
        """Initialize the template engine with Jinja2 environment.

        Configures the Jinja2 environment to load templates from the
        notification_service package's templates directory with HTML
        auto-escaping enabled for security.
        """
        self._env = Environment(
            loader=PackageLoader("notification_service", "templates"),
            autoescape=select_autoescape(["html"]),
        )

    def render_sms(self, template_id: str, variables: dict) -> str:
        """Render an SMS template with the provided variables.

        Args:
            template_id: The template identifier (e.g., 'consent_request').
            variables: A dictionary of template variables for substitution.

        Returns:
            The rendered SMS message text.
        """
        template_path = f"sms/{template_id}.txt"
        log = logger.bind(template_path=template_path)
        log.info("Rendering SMS template")

        template = self._env.get_template(template_path)
        rendered = template.render(**variables)

        log.info("SMS template rendered successfully", length=len(rendered))
        return rendered

    def render_email_html(self, template_id: str, variables: dict) -> str:
        """Render an HTML email template with the provided variables.

        Args:
            template_id: The template identifier (e.g., 'consent_request').
            variables: A dictionary of template variables for substitution.

        Returns:
            The rendered HTML email body.
        """
        template_path = f"email/{template_id}.html"
        log = logger.bind(template_path=template_path)
        log.info("Rendering HTML email template")

        template = self._env.get_template(template_path)
        rendered = template.render(**variables)

        log.info("HTML email template rendered successfully", length=len(rendered))
        return rendered

    def render_email_text(self, template_id: str, variables: dict) -> str:
        """Render a plain text email template with the provided variables.

        Args:
            template_id: The template identifier (e.g., 'consent_request').
            variables: A dictionary of template variables for substitution.

        Returns:
            The rendered plain text email body.
        """
        template_path = f"email/{template_id}.txt"
        log = logger.bind(template_path=template_path)
        log.info("Rendering text email template")

        template = self._env.get_template(template_path)
        rendered = template.render(**variables)

        log.info("Text email template rendered successfully", length=len(rendered))
        return rendered
