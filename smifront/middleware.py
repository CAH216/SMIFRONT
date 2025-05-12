# middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)


class UserSessionMiddleware:
    """
    Middleware pour gérer la session utilisateur et vérifier l'authentification
    pour les routes protégées.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Routes qui ne nécessitent pas d'authentification
        self.public_routes = [
            '',
            '/login/',
            '/logout/',
            '/signup/',
            '/password-reset/',
            '/static/',
            '/media/',
            '/admin/',
            '/api/',
            '/verify-account/',
        ]

    def __call__(self, request):
        # Vérifier si l'utilisateur est authentifié pour les routes protégées
        path = request.path

        # Vérifier si la route actuelle est publique
        if not any(path.startswith(route) for route in self.public_routes):
            # Vérifier si l'utilisateur est connecté via la session
            user_id = request.session.get('user_id')
            if not user_id:
                logger.warning(f"Accès non autorisé à {path}. Redirection vers la page de connexion.")
                messages.warning(request, "Veuillez vous connecter pour accéder à cette page.")
                return redirect(reverse('login') + f"?next={path}")

        # Ajouter les informations utilisateur à toutes les requêtes
        request.user_id = request.session.get('user_id')
        request.user_role = request.session.get('user_role')
        request.user_name = request.session.get('user_name')
        request.user_email = request.session.get('user_email')

        response = self.get_response(request)
        return response