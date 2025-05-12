import csv
import io
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
import logging
import xlsxwriter
from xhtml2pdf import pisa
from django.template.loader import get_template

from .api_client import APIClient, APIException
from django.views.decorators.csrf import csrf_protect

logger = logging.getLogger(__name__)


# views.py
def index(request):
    search_query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')

    try:
        # Initialisation du client API avec l'ID et token de l'utilisateur connecté
        api_client = APIClient(user_id=request.user_id)

        # Récupération des catégories
        categories = api_client.get_all_categories()

        # Pour chaque catégorie, récupérer le nombre de produits
        for category in categories:
            try:
                # Récupérer les produits pour cette catégorie
                products = api_client.get_products_by_category(category['id'])
                category['product_count'] = len(products) if products else 0
            except APIException:
                category['product_count'] = 0

        # Récupérer tous les produits pour l'affichage ou la recherche
        all_products = []
        try:
            if category_filter:
                all_products = api_client.get_products_by_category(category_filter)
            else:
                # Récupérer tous les produits de toutes les catégories
                for category in categories:
                    products = api_client.get_products_by_category(category['id'])
                    if products:
                        for product in products:
                            product['category_name'] = category['nom']
                        all_products.extend(products)

            # Filtrer les produits si une recherche est en cours
            if search_query:
                all_products = [p for p in all_products if search_query.lower() in p['nom'].lower()]

        except APIException:
            all_products = []

        context = {
            'categories': categories,
            'products': all_products,
            'search_query': search_query,
            'category_filter': category_filter
        }

        return render(request, 'index.html', context)

    except APIException as e:
        messages.error(request, str(e))
        return render(request, 'index.html', {'categories': [], 'products': []})


def signup_view(request):
    """Vue pour la page d'inscription"""
    # Si l'utilisateur est déjà connecté, le rediriger vers la page d'accueil
    if request.session.get('user_id'):
        return redirect('index')

    if request.method == 'POST':
        # Récupération des données du formulaire
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        # Validation des données
        if not all([nom, prenom, email, password, password_confirm]):
            messages.error(request, "Tous les champs sont obligatoires.")
            return render(request, 'signup.html', {
                'nom': nom,
                'prenom': prenom,
                'email': email
            })

        if password != password_confirm:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, 'signup.html', {
                'nom': nom,
                'prenom': prenom,
                'email': email
            })

        try:
            # Vérifier si l'email existe déjà
            client = APIClient()
            email_exists = client.check_email_exists(email)

            if email_exists:
                messages.error(request, "Cet email est déjà utilisé. Veuillez en choisir un autre.")
                return render(request, 'signup.html', {
                    'nom': nom,
                    'prenom': prenom
                })

            # Inscription de l'utilisateur
            response = client.signup(nom, prenom, email, password)

            # Vérifier si l'inscription a réussi
            if isinstance(response, dict) and 'id' in response:
                # Connecter automatiquement l'utilisateur
                request.session['user_id'] = response['id']
                request.session['user_role'] = response.get('role', 'EMPLOYE')
                request.session['user_name'] = f"{response.get('prenom', '')} {response.get('nom', '')}"
                request.session['user_email'] = response.get('email', '')

                # Journaliser l'inscription réussie
                logger.info(f"Inscription réussie pour l'utilisateur {email} (ID: {response['id']})")

                messages.success(request, "Inscription réussie ! Bienvenue sur notre plateforme.")
                return redirect('index')
            else:
                # La réponse n'a pas le format attendu
                logger.warning(f"Format de réponse inattendu lors de l'inscription: {response}")
                messages.error(request, "Une erreur est survenue lors de l'inscription. Veuillez réessayer.")

        except APIException as e:
            # Gestion des erreurs d'API
            logger.error(f"Erreur lors de l'inscription pour {email}: {str(e)}")
            messages.error(request, f"Erreur d'inscription: {str(e)}")

        except Exception as e:
            # Gestion des autres erreurs
            logger.error(f"Erreur inattendue lors de l'inscription: {str(e)}")
            messages.error(request, "Une erreur inattendue s'est produite. Veuillez réessayer ultérieurement.")

    return render(request, 'signup.html')


# Décorateur pour vérifier que l'utilisateur est admin ou gérant
def admin_required(view_func):
    """
    Décorateur qui vérifie que l'utilisateur connecté est un SUPER_ADMIN ou un GERANT.
    Redirige vers la page d'accueil si ce n'est pas le cas.
    """

    def _wrapped_view(request, *args, **kwargs):
        # Vérifier que la session contient des données
        if not request.session or 'user_role' not in request.session:
            messages.error(request, "Session invalide ou expirée. Veuillez vous reconnecter.")
            return redirect('index')

        # Vérifier les rôles autorisés
        if request.session.get('user_role') in ['SUPER_ADMIN', 'GERANT']:
            return view_func(request, *args, **kwargs)

        messages.error(request, "Vous n'avez pas les permissions nécessaires pour accéder à cette page.")
        return redirect('index')

    return _wrapped_view


def employe_required(view_func):
    """
    Décorateur qui vérifie que l'utilisateur connecté est un SUPER_ADMIN ou un GERANT.
    Redirige vers la page d'accueil si ce n'est pas le cas.
    """

    def _wrapped_view(request, *args, **kwargs):
        # Vérifier que la session contient des données
        if not request.session:
            messages.error(request, "Session invalide ou expirée. Veuillez vous reconnecter.")
            return redirect('index')

    return _wrapped_view


# Décorateur pour vérifier que l'utilisateur est super admin
def super_admin_required(view_func):
    """
    Décorateur qui vérifie que l'utilisateur connecté est un SUPER_ADMIN.
    Redirige vers la page d'accueil si ce n'est pas le cas.
    """

    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.session.get('user_role') == 'SUPER_ADMIN':
            return view_func(request, *args, **kwargs)
        messages.error(request, "Vous n'avez pas les permissions nécessaires pour accéder à cette page.")
        return redirect('index')

    return _wrapped_view


@login_required
def dashboard_view(request):
    """Vue pour la page dashboard principale"""
    # Rediriger vers le dashboard approprié selon le rôle
    user_role = request.session.get('user_role')

    if user_role in ['SUPER_ADMIN', 'GERANT']:
        return redirect('admin_dashboard')
    else:
        return redirect('user_dashboard')


@admin_required
def admin_dashboard_view(request):
    """Vue pour le dashboard administrateur"""
    return render(request, 'dashboard/admin/users.html')


@login_required
def user_dashboard_view(request):
    """Vue pour le dashboard utilisateur normal"""
    return render(request, 'dashboard/admin/users.html')


@admin_required
def admin_categories(request):
    """Vue pour afficher la liste des catégories"""
    try:
        # Initialisation du client API avec l'ID et token de l'utilisateur connecté
        api_client = APIClient(user_id=request.user_id)

        # Récupération des catégories
        categories = api_client.get_all_categories()

        # Pour chaque catégorie, récupérer le nombre de produits
        for category in categories:
            try:
                # Récupérer les produits pour cette catégorie
                products = api_client.get_products_by_category(category['id'])
                category['product_count'] = len(products) if products else 0
            except APIException:
                category['product_count'] = 0

        context = {
            'categories': categories,
            'active_page': 'categories',
        }

        return render(request, 'dashboard/admin/categories.html', context)

    except APIException as e:
        messages.error(request, str(e))
        return render(request, 'dashboard/admin/categories.html', {'categories': [], 'active_page': 'categories'})


@admin_required
@require_http_methods(["POST"])
def admin_categories_create(request):
    """Vue pour créer une nouvelle catégorie"""
    try:
        nom = request.POST.get('nom')

        if not nom:
            messages.error(request, "Le nom de la catégorie est requis")
            return redirect('admin_categories')

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Vérifier si le nom existe déjà
        name_check = api_client.check_category_name_exists(nom)
        if name_check and name_check.get('exists'):
            messages.error(request, "Ce nom de catégorie existe déjà")
            return redirect('admin_categories')

        # Créer la catégorie
        api_client.create_category(nom)

        messages.success(request, "Catégorie créée avec succès")

    except APIException as e:
        messages.error(request, str(e))

    return redirect('admin_categories')


@admin_required
@require_http_methods(["POST"])
def admin_categories_update(request):
    """Vue pour mettre à jour une catégorie existante"""
    try:
        category_id = request.POST.get('category_id')
        nom = request.POST.get('nom')

        if not category_id or not nom:
            messages.error(request, "Paramètres manquants")
            return redirect('admin_categories')

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Vérifier si le nom existe déjà pour une autre catégorie
        name_check = api_client.check_category_name_exists(nom)

        # Si le nom existe et appartient à une autre catégorie
        if name_check:
            messages.error(request, "Ce nom de catégorie existe déjà")
            return redirect('admin_categories')

        # Mettre à jour la catégorie
        api_client.update_category(category_id, nom)

        messages.success(request, "Catégorie mise à jour avec succès")

    except APIException as e:
        messages.error(request, str(e))

    return redirect('admin_categories')


@admin_required
@require_http_methods(["POST"])
def admin_categories_delete(request):
    """Vue pour supprimer une catégorie"""
    try:
        category_id = request.POST.get('category_id')

        if not category_id:
            messages.error(request, "ID de catégorie manquant")
            return redirect('admin_categories')

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Supprimer la catégorie
        api_client.delete_category(category_id)

        messages.success(request, "Catégorie supprimée avec succès")

    except APIException as e:
        messages.error(request, str(e))

    return redirect('admin_categories')


@admin_required
def admin_check_category_name(request):
    """Vue pour vérifier si un nom de catégorie existe déjà"""
    try:
        nom = request.GET.get('nom')

        if not nom:
            return JsonResponse({"exists": False})

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Vérifier si le nom existe
        result = api_client.check_category_name_exists(nom)

        return JsonResponse({"exists": result.get('exists', False)})

    except APIException as e:
        return JsonResponse({"exists": False, "error": str(e)})


@admin_required
def admin_products(request):
    """Vue pour afficher la liste des produits"""
    try:
        # Initialisation du client API avec l'ID et token de l'utilisateur connecté
        api_client = APIClient(user_id=request.user_id)

        # Récupération des produits
        products = api_client.get_all_products()

        # Récupération des catégories pour le formulaire
        categories = api_client.get_all_categories()

        # Ajouter l'URL d'image pour chaque produit
        for product in products:
            if 'image' in product and product['image']:
                # Si l'API renvoie déjà une URL d'image complète
                if product['image'].startswith('http'):
                    product['image_url'] = product['image']
                else:
                    # Sinon, construire l'URL
                    product['image_url'] = f"{settings.API_BASE_URL}/produits/{product['id']}/image"
            else:
                product['image_url'] = None

        context = {
            'products': products,
            'categories': categories,
            'active_page': 'products',
        }

        return render(request, 'dashboard/admin/products.html', context)

    except APIException as e:
        messages.error(request, str(e))
        return render(request, 'dashboard/admin/products.html',
                      {'products': [], 'categories': [], 'active_page': 'products'})


@admin_required
@require_http_methods(["POST"])
def admin_products_create(request):
    """Vue pour créer un nouveau produit"""
    try:
        nom = request.POST.get('nom')
        prix = request.POST.get('prix')
        description = request.POST.get('description')
        categorie_id = request.POST.get('categorie_id')
        statut = request.POST.get('statut', 'VALIDE')

        if not nom or not prix or not categorie_id:
            messages.error(request, "Tous les champs obligatoires doivent être remplis")
            return redirect('admin_products')

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Vérifier si le nom existe déjà
        name_check = api_client.check_product_name_exists(nom)
        if name_check:
            messages.error(request, "Ce nom de produit existe déjà")
            return redirect('admin_products')

        # Traitement de l'image
        image_file = request.FILES.get('image')

        # Créer le produit avec l'image téléchargée
        product = api_client.create_product(
            nom=nom,
            description=description,
            prix=prix,
            categorie_id=categorie_id,
            image_file=image_file
        )

        if product:
            # Une fois créé, mettre à jour le statut si nécessaire
            if statut and statut != 'VALIDE':
                api_client.update_product_status(product['id'], statut)

            messages.success(request, "Produit créé avec succès")
        else:
            messages.error(request, "Erreur lors de la création du produit")

    except APIException as e:
        messages.error(request, str(e))

    return redirect('admin_products')


@admin_required
@require_http_methods(["POST"])
def admin_products_update(request):
    """Vue pour mettre à jour un produit existant"""
    try:
        product_id = request.POST.get('product_id')
        nom = request.POST.get('nom')
        prix = request.POST.get('prix')
        description = request.POST.get('description')
        categorie_id = request.POST.get('categorie_id')
        statut = request.POST.get('statut')

        if not product_id or not nom or not prix or not categorie_id:
            messages.error(request, "Tous les champs obligatoires doivent être remplis")
            return redirect('admin_products')

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Vérifier si le nom existe déjà
        name_check = api_client.check_product_name_exists(nom)
        if name_check:
            messages.error(request, "Ce nom de produit existe déjà")
            return redirect('admin_products')

        # Gestion de l'image
        image_file = request.FILES.get('image')
        image_changed = request.POST.get('image_changed') == 'true'
        image_removed = request.POST.get('image_removed') == 'true'
        library_image_id = request.POST.get('library_image_id')

        if image_removed:
            # Supprimer l'image existante
            # Cela dépend de la façon dont votre API gère la suppression d'image
            # Ici, on suppose qu'il y a une méthode pour mettre à jour un produit sans image
            product = api_client.update_product(
                product_id=product_id,
                nom=nom,
                description=description,
                prix=prix,
                categorie_id=categorie_id,
                remove_image=True
            )
        elif library_image_id:
            # Utiliser une image de la bibliothèque
            product = api_client.update_product(
                product_id=product_id,
                nom=nom,
                description=description,
                prix=prix,
                categorie_id=categorie_id,
                library_image_id=library_image_id
            )
        elif image_file:
            # Mettre à jour avec une nouvelle image
            product = api_client.update_product(
                product_id=product_id,
                nom=nom,
                description=description,
                prix=prix,
                categorie_id=categorie_id,
                image_file=image_file
            )
        else:
            # Mettre à jour sans changer l'image
            product = api_client.update_product(
                product_id=product_id,
                nom=nom,
                description=description,
                prix=prix,
                categorie_id=categorie_id
            )

        # Mettre à jour le statut si nécessaire
        current_product = api_client.get_product(product_id)
        if statut and current_product.get('statut') != statut:
            api_client.update_product_status(product_id, statut)

        messages.success(request, "Produit mis à jour avec succès")

    except APIException as e:
        messages.error(request, str(e))

    return redirect('admin_products')


@admin_required
@require_http_methods(["POST"])
def admin_products_delete(request):
    """Vue pour supprimer un produit"""
    try:
        product_id = request.POST.get('product_id')

        if not product_id:
            messages.error(request, "ID du produit manquant")
            return redirect('admin_products')

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Supprimer le produit
        api_client.delete_product(product_id)

        messages.success(request, "Produit supprimé avec succès")

    except APIException as e:
        messages.error(request, str(e))

    return redirect('admin_products')


@admin_required
@require_http_methods(["POST"])
def admin_products_status(request):
    """Vue pour mettre à jour le statut d'un produit"""
    try:
        product_id = request.POST.get('product_id')
        status = request.POST.get('status')

        if not product_id or not status:
            return JsonResponse({'success': False, 'message': 'Paramètres manquants'}, status=400)

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Mettre à jour le statut
        api_client.update_product_status(product_id, status)

        return JsonResponse({'success': True, 'message': 'Statut mis à jour avec succès'})

    except APIException as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@admin_required
def admin_check_product_name(request):
    """Vue pour vérifier si un nom de produit existe déjà"""
    try:
        nom = request.GET.get('nom')

        if not nom:
            return JsonResponse({"exists": False})

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Vérifier si le nom existe
        result = api_client.check_product_name_exists(nom)

        return JsonResponse({"exists": result.get('exists', False)})

    except APIException as e:
        return JsonResponse({"exists": False, "error": str(e)})


@admin_required
def admin_product_image(request, product_id):
    """Vue pour récupérer l'image d'un produit"""
    try:
        if not product_id:
            return HttpResponse(status=400)

        # Initialisation du client API
        api_client = APIClient(user_id=request.user_id)

        # Récupérer l'image
        image_data = api_client.get_product_image(product_id)

        if image_data:
            # Déterminer le type MIME (cela pourrait être fourni par l'API)
            mime_type = "image/jpeg"  # Par défaut

            response = HttpResponse(image_data, content_type=mime_type)
            response['Content-Disposition'] = f'inline; filename="product_{product_id}.jpg"'
            return response
        else:
            return HttpResponse(status=404)

    except APIException as e:
        return HttpResponse(status=500)


@admin_required
def admin_users_create(request):
    """Vue pour créer un nouvel utilisateur"""
    # Vérifier si l'utilisateur est connecté et a les droits nécessaires
    if not request.user_id:
        messages.error(request, "Vous devez être connecté pour accéder à cette page.")
        return redirect('login')

    # Vérifier les permissions
    if request.user_role not in ['SUPER_ADMIN', 'GERANT']:
        messages.error(request, "Vous n'avez pas les permissions nécessaires pour créer un utilisateur.")
        return redirect('admin_users')

    # Traiter la requête POST pour la création d'utilisateur
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            nom = request.POST.get('nom')
            prenom = request.POST.get('prenom')
            email = request.POST.get('email')
            password = request.POST.get('password')
            role = request.POST.get('role')
            statut = request.POST.get('statut')

            # Valider les données
            if not all([nom, prenom, email, password, role, statut]):
                messages.error(request, "Tous les champs sont obligatoires.")
                return redirect('admin_users')

            # Créer un client API
            client = APIClient(user_id=request.user_id)

            # Vérifier si l'email existe déjà
            email_check = client.check_email_exists(email)
            if email_check:
                messages.error(request, "Cet email est déjà utilisé.")
                return redirect('dashboard')

            # Créer l'utilisateur via l'API
            user_data = client.signup(nom, prenom, email, password, role)

            # Si le statut n'est pas 'A' (Actif par défaut), mettre à jour le statut
            if statut != 'A' and 'id' in user_data:
                client.update_user_status(user_data['id'], statut)

            messages.success(request, "L'utilisateur a été créé avec succès.")
            return redirect('dashboard')

        except APIException as e:
            logger.error(f"Erreur API dans admin_users_create: {str(e)}")
            messages.error(request, f"Erreur lors de la création de l'utilisateur: {str(e)}")
            return redirect('dashboard')

        except Exception as e:
            logger.error(f"Erreur inattendue dans admin_users_create: {str(e)}")
            messages.error(request, "Une erreur inattendue s'est produite lors de la création de l'utilisateur.")
            return redirect('dashboard')

    # Si ce n'est pas une requête POST, rediriger vers la liste des utilisateurs
    return redirect('dashboard')


@admin_required
def admin_users_update(request):
    """Vue pour mettre à jour un utilisateur existant"""
    # Vérifier si l'utilisateur est connecté et a les droits nécessaires
    if not request.user_id:
        messages.error(request, "Vous devez être connecté pour accéder à cette page.")
        return redirect('login')

    # Vérifier les permissions
    if request.user_role not in ['SUPER_ADMIN', 'GERANT']:
        messages.error(request, "Vous n'avez pas les permissions nécessaires pour modifier un utilisateur.")
        return redirect('dashboard')

    # Traiter la requête POST pour la mise à jour d'utilisateur
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            user_id = request.POST.get('user_id')
            nom = request.POST.get('nom')
            prenom = request.POST.get('prenom')
            email = request.POST.get('email')
            password = request.POST.get('password')
            role = request.POST.get('role')
            statut = request.POST.get('statut')

            # Valider les données obligatoires
            if not all([user_id, nom, prenom, email, role, statut]):
                messages.error(request, "Les champs nom, prénom, email, rôle et statut sont obligatoires.")
                return redirect('dashboard')

            # Créer un client API
            client = APIClient(user_id=request.user_id)

            # Préparer les données de mise à jour
            update_data = {
                'id': user_id,
                'nom': nom,
                'prenom': prenom,
                'email': email,
                'role': role,
                'statut': statut
            }

            # Si un nouveau mot de passe est fourni, l'ajouter aux données
            if password:
                update_data['mot_de_passe'] = password

            # Mettre à jour l'utilisateur via l'API
            client.update_user(request.user_id, update_data)

            messages.success(request, "L'utilisateur a été mis à jour avec succès.")
            return redirect('dashboard')

        except APIException as e:
            logger.error(f"Erreur API dans admin_users_update: {str(e)}")
            messages.error(request, f"Erreur lors de la mise à jour de l'utilisateur: {str(e)}")
            return redirect('dashboard')

        except Exception as e:
            logger.error(f"Erreur inattendue dans admin_users_update: {str(e)}")
            messages.error(request, "Une erreur inattendue s'est produite lors de la mise à jour de l'utilisateur.")
            return redirect('dashboard')

    # Si ce n'est pas une requête POST, rediriger vers la liste des utilisateurs
    return redirect('dashboard')


@admin_required
def admin_users_delete(request):
    """Vue pour supprimer un utilisateur"""
    # Vérifier si l'utilisateur est connecté et a les droits nécessaires
    if not request.user_id:
        messages.error(request, "Vous devez être connecté pour accéder à cette page.")
        return redirect('login')

    # Vérifier les permissions
    if request.user_role not in ['SUPER_ADMIN']:
        messages.error(request, "Seuls les super administrateurs peuvent supprimer des utilisateurs.")
        return redirect('dashboard')

    # Traiter la requête POST pour la suppression d'utilisateur
    if request.method == 'POST':
        try:
            # Récupérer l'ID de l'utilisateur à supprimer
            user_id = request.POST.get('user_id')

            if not user_id:
                messages.error(request, "ID utilisateur non spécifié.")
                return redirect('dashboard')

            # Vérifier que l'utilisateur ne se supprime pas lui-même
            if str(user_id) == str(request.user_id):
                messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
                return redirect('dashboard')

            # Créer un client API
            client = APIClient(user_id=request.user_id)

            # Supprimer l'utilisateur via l'API
            client.delete_user(user_id)

            messages.success(request, "L'utilisateur a été supprimé avec succès.")
            return redirect('dashboard')

        except APIException as e:
            logger.error(f"Erreur API dans admin_users_delete: {str(e)}")
            messages.error(request, f"Erreur lors de la suppression de l'utilisateur: {str(e)}")
            return redirect('dashboard')

        except Exception as e:
            logger.error(f"Erreur inattendue dans admin_users_delete: {str(e)}")
            messages.error(request, "Une erreur inattendue s'est produite lors de la suppression de l'utilisateur.")
            return redirect('dashboard')

    # Si ce n'est pas une requête POST, rediriger vers la liste des utilisateurs
    return redirect('dashboard')






@csrf_protect
def admin_products_status(request):
    """Vue pour mettre à jour le statut d'un produit"""

    # Vérifier que c'est une requête POST
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Méthode non autorisée'
        }, status=405)

    # Vérifier si l'utilisateur est connecté
    if not hasattr(request, 'user_id') or not request.user_id:
        return JsonResponse({
            'success': False,
            'message': 'Vous devez être connecté pour effectuer cette action.'
        }, status=401)

    # Vérifier les permissions
    if request.user_role not in ['SUPER_ADMIN', 'GERANT']:
        return JsonResponse({
            'success': False,
            'message': 'Vous n\'avez pas les permissions nécessaires pour modifier le statut d\'un produit.'
        }, status=403)

    try:
        # Récupérer les données du formulaire
        product_id = request.POST.get('product_id')
        status = request.POST.get('status')

        # Valider les données
        if not product_id or not status:
            return JsonResponse({
                'success': False,
                'message': 'L\'ID du produit et le statut sont requis.'
            }, status=400)

        # Valider le statut
        valid_statuses = ['VALIDE', 'INACTIF', 'EN_ATTENTE']
        if status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'message': f'Statut invalide. Les statuts valides sont : {", ".join(valid_statuses)}'
            }, status=400)

        # Convertir l'ID en entier
        try:
            product_id = int(product_id)
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'ID de produit invalide.'
            }, status=400)

        # Créer un client API
        client = APIClient(user_id=request.user_id)

        # Mettre à jour le statut via l'API
        result = client.update_product_status(product_id, status)

        # Log l'action
        logger.info(f"Statut du produit {product_id} mis à jour vers {status} par l'utilisateur {request.user_id}")

        return JsonResponse({
            'success': True,
            'message': 'Le statut du produit a été mis à jour avec succès.',
            'new_status': status,
            'result': result
        })

    except APIException as e:
        logger.error(f"Erreur API dans admin_products_status: {str(e)}")

        # Vérifier si c'est une erreur 404 (produit non trouvé)
        if "404" in str(e):
            return JsonResponse({
                'success': False,
                'message': 'Produit non trouvé.'
            }, status=404)

        return JsonResponse({
            'success': False,
            'message': f'Erreur lors de la mise à jour du statut: {str(e)}'
        }, status=500)

    except Exception as e:
        logger.error(f"Erreur inattendue dans admin_products_status: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Une erreur inattendue s\'est produite.'
        }, status=500)

def employe_products_create(request):
    """Vue pour créer un nouveau produit"""
    # Vérifier si l'utilisateur est connecté
    if not request.user_id:
        messages.error(request, "Vous devez être connecté pour accéder à cette page.")
        return redirect('login')

    # Vérifier les permissions - les employés peuvent créer des produits
    if request.user_role not in ['SUPER_ADMIN', 'GERANT', 'EMPLOYE']:
        messages.error(request, "Vous n'avez pas les permissions nécessaires pour créer un produit.")
        return redirect('dashboard')

    # Afficher le formulaire pour les employés
    if request.user_role == 'EMPLOYE' and request.method == 'GET':
        try:
            # Créer un client API
            client = APIClient(user_id=request.user_id)

            # Récupérer les catégories pour le formulaire
            categories = client.get_all_categories()

            context = {
                'categories': categories,
                'request': request
            }

            return render(request, 'dashboard/employe/dashboard.html', context)

        except APIException as e:
            logger.error(f"Erreur API lors de la récupération des catégories: {str(e)}")
            messages.error(request, "Erreur lors du chargement des catégories.")
            return redirect('dashboard/employe/dashboard.html')

    # Traiter la requête POST pour la création de produit
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            nom = request.POST.get('nom')
            prix = request.POST.get('prix')
            categorie_id = request.POST.get('categorie_id')
            statut = "EN_ATTENTE"
            description = request.POST.get('description', '')

            # Valider les données obligatoires
            if not all([nom, prix, categorie_id]):
                return JsonResponse({
                    'success': False,
                    'message': "Les champs nom, prix et catégorie sont obligatoires."
                }, status=400)

            # Convertir le prix en float
            try:
                prix = float(prix)
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': "Le prix doit être un nombre valide."
                }, status=400)

            # Créer un client API
            client = APIClient(user_id=request.user_id)

            # Préparer les données du produit
            product_data = {
                'nom': nom,
                'prix': prix,
                'categorie_id': int(categorie_id),
                'statut': statut,
                'description': description
            }

            # Gérer l'upload de l'image si présente
            if 'image' in request.FILES:
                image_file = request.FILES['image']

                # Valider le type de fichier
                allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
                if image_file.content_type not in allowed_types:
                    return JsonResponse({
                        'success': False,
                        'message': "Type de fichier non autorisé. Utilisez JPG, PNG ou GIF."
                    }, status=400)

                # Valider la taille du fichier (max 5MB)
                if image_file.size > 5 * 1024 * 1024:
                    return JsonResponse({
                        'success': False,
                        'message': "L'image est trop volumineuse (max 5MB)."
                    }, status=400)

                # Ajouter l'image aux données
                product_data['image'] = image_file

            result = client.create_product(
                nom=product_data['nom'],
                description=product_data['description'],
                prix=product_data['prix'],
                categorie_id=product_data['categorie_id'],
                image_file=product_data['image']
            )

            # Retourner une réponse JSON pour AJAX
            return JsonResponse({
                'success': True,
                'message': "Produit créé avec succès!",
                'product_id': result.get('id')
            })

        except APIException as e:
            logger.error(f"Erreur API dans employe_products_create: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f"Erreur lors de la création du produit: {str(e)}"
            }, status=500)

        except Exception as e:
            logger.error(f"Erreur inattendue dans employe_products_create: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': "Une erreur inattendue s'est produite lors de la création du produit."
            }, status=500)

    # Pour les autres cas, rediriger vers le dashboard
    return redirect('dashboard/employe/dashboard.html')


def employee_dashboard(request):
    """Vue pour afficher le dashboard des employés"""
    # Vérifier si l'utilisateur est connecté et est un employé
    if not request.user_id:
        messages.error(request, "Vous devez être connecté pour accéder à cette page.")
        return redirect('login')

    if request.user_role != 'EMPLOYE':
        messages.error(request, "Cette page est réservée aux employés.")
        return redirect('dashboard')

    try:
        # Créer un client API
        client = APIClient(user_id=request.user_id)

        # Récupérer les catégories pour le formulaire
        categories = client.get_all_categories()

        context = {
            'categories': categories,
            'request': request
        }

        return render(request, 'dashboard/employe/dashboard.html', context)

    except APIException as e:
        logger.error(f"Erreur API dans employee_dashboard: {str(e)}")
        messages.error(request, "Erreur lors du chargement du dashboard.")
        return redirect('dashboard/employe/dashboard.html')

    except Exception as e:
        logger.error(f"Erreur inattendue dans employee_dashboard: {str(e)}")
        messages.error(request, "Une erreur inattendue s'est produite.")
        return redirect('dashboard/employe/dashboard.html')
