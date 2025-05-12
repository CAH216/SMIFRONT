# exception_handler.py
import sys
import traceback
import logging
from django.views.debug import ExceptionReporter
from django.conf import settings
from django.core.mail import mail_admins
from django.http import HttpResponseServerError
from django.template import loader
from django.urls import resolve

logger = logging.getLogger(__name__)


class GlobalExceptionHandler:
    """Gestionnaire global d'exceptions pour capturer toutes les erreurs"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Journaliser l'erreur
            logger.error(f"Exception non gérée: {str(e)}", exc_info=True)

            # Envoyer un email de notification
            self.notify_exception(request, e)

            # Afficher une page d'erreur conviviale
            return self.handle_exception(request, e)

    def notify_exception(self, request, exception):
        """Envoie une notification par email pour l'exception"""
        if not settings.ALERT_EMAILS_ENABLED:
            return

        try:
            # Récupérer les informations sur l'erreur
            exc_info = sys.exc_info()

            # Récupérer la vue qui a généré l'erreur
            try:
                resolver_match = resolve(request.path)
                view_name = resolver_match.func.__name__
            except:
                view_name = "Inconnue"

            # Générer un rapport d'exception
            reporter = ExceptionReporter(request, *exc_info)
            html_message = reporter.get_traceback_html()

            # Créer le sujet de l'email
            subject = f"❌ ERREUR {settings.SITE_NAME} - {exception.__class__.__name__}"

            # Générer le message texte
            message = (
                f"Une exception non gérée s'est produite: {exception.__class__.__name__}\n\n"
                f"URL: {request.build_absolute_uri()}\n"
                f"Vue: {view_name}\n"
                f"Utilisateur: {getattr(request, 'user_id', 'Non connecté')}\n\n"
                f"Message d'erreur: {str(exception)}\n\n"
                f"Traceback:\n{traceback.format_exc()}\n\n"
                f"Cette alerte est générée automatiquement par {settings.SITE_NAME}."
            )

            # Envoyer l'email
            mail_admins(
                subject=subject,
                message=message,
                html_message=html_message,
                fail_silently=True
            )

            logger.info(f"Email de notification d'erreur envoyé à {settings.ALERT_ADMIN_EMAIL}")

        except Exception as mail_error:
            logger.error(f"Impossible d'envoyer l'email de notification d'erreur: {str(mail_error)}")

    def handle_exception(self, request, exception):
        """Affiche une page d'erreur conviviale"""
        template = loader.get_template('error.html')

        # Contexte pour le template d'erreur
        is_admin = getattr(request, 'user_role', '') in ['SUPER_ADMIN', 'GERANT']
        is_debug = settings.DEBUG

        context = {
            'error_message': str(exception),
            'error_type': exception.__class__.__name__,
            'show_details': is_admin or is_debug,
            'traceback': traceback.format_exc() if (is_admin or is_debug) else None,
        }

        # Rendu du template
        return HttpResponseServerError(template.render(context, request))