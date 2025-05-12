# views_dashboard.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import json
import logging
from .api_client import APIClient, APIException

logger = logging.getLogger(__name__)


def dashboard_view(request):
    """Vue principale du dashboard"""
    # Vérifier si l'utilisateur est connecté
    if not request.user_id:
        messages.error(request, "Vous devez être connecté pour accéder au dashboard.")
        return redirect('login')

    try:
        # Créer le client API avec l'ID utilisateur
        client = APIClient(user_id=request.user_id)

        # Récupérer les données nécessaires pour le dashboard
        # Si l'utilisateur est admin ou gérant, récupérer toutes les données
        if request.user_role in ['SUPER_ADMIN', 'GERANT']:
            users = client.get_all_users()
        else:
            users = []

        # Récupérer les catégories
        categories = client.get_all_categories()

        # Récupérer les produits
        products = client.get_all_products()

        # Préparer le contexte pour le template
        context = {
            'users': users,
            'categories': categories,
            'products': products,
            'active_page': 'users'
        }

        return render(request, 'dashboard/admin/users.html', context)

    except APIException as e:
        # Gestion des erreurs d'API
        logger.error(f"Erreur API dans le dashboard: {str(e)}")
        messages.error(request, f"Erreur lors du chargement des données: {str(e)}")
        return render(request, 'dashboard/admin/users.html', {'error': str(e)})

    except Exception as e:
        # Gestion des autres erreurs
        logger.error(f"Erreur inattendue dans le dashboard: {str(e)}")
        messages.error(request, "Une erreur inattendue s'est produite. Veuillez réessayer.")
        return render(request, 'dashboard/admin/users.html', {'error': "Une erreur inattendue s'est produite."})



