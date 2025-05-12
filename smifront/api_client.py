import requests
import json
import logging
from django.conf import settings
from django.core.mail import send_mail
import traceback
from functools import wraps
from datetime import datetime

# Configuration du logging
logger = logging.getLogger(__name__)

# Base URL pour les API
API_BASE_URL = settings.API_BASE_URL


def notify_error(error_message, endpoint, exception_details, data=None):
    """
    Envoie un email de notification en cas d'erreur
    """
    if not settings.ALERT_EMAILS_ENABLED:
        logger.warning("Les alertes par email sont désactivées. Erreur non notifiée.")
        return False

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    subject = f"⚠️ ERREUR API {settings.SITE_NAME} - {timestamp}"

    message = (
        f"Une erreur est survenue lors de l'appel à l'API: {endpoint}\n\n"
        f"Timestamp: {timestamp}\n"
        f"Erreur: {error_message}\n\n"
        f"Détails de l'exception:\n{exception_details}\n\n"
    )

    if data:
        message += f"Données envoyées:\n{json.dumps(data, indent=2, ensure_ascii=False)}\n\n"

    message += f"Cette alerte est générée automatiquement par {settings.SITE_NAME}."

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ALERT_ADMIN_EMAIL],
            fail_silently=False,
        )
        logger.info(f"Email de notification envoyé à {settings.ALERT_ADMIN_EMAIL}")
        return True
    except Exception as mail_error:
        logger.error(f"Impossible d'envoyer l'email de notification: {str(mail_error)}")
        return False


def handle_api_errors(func):
    """
    Décorateur pour gérer les erreurs d'API et envoyer des notifications
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.ConnectionError as e:
            error_msg = "Impossible de se connecter à l'API"
            logger.error(f"{error_msg}: {str(e)}")
            notify_error(error_msg, func.__name__, traceback.format_exc(), kwargs.get('data'))
            raise APIException(error_msg)
        except requests.exceptions.Timeout as e:
            error_msg = "Délai d'attente dépassé lors de la connexion à l'API"
            logger.error(f"{error_msg}: {str(e)}")
            notify_error(error_msg, func.__name__, traceback.format_exc(), kwargs.get('data'))
            raise APIException(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Erreur lors de la requête à l'API: {str(e)}"
            logger.error(error_msg)
            notify_error(error_msg, func.__name__, traceback.format_exc(), kwargs.get('data'))
            raise APIException(error_msg)
        except Exception as e:
            error_msg = f"Erreur inattendue: {str(e)}"
            logger.error(error_msg)
            notify_error(error_msg, func.__name__, traceback.format_exc(), kwargs.get('data'))
            raise APIException(error_msg)

    return wrapper


class APIException(Exception):
    """Exception personnalisée pour les erreurs d'API"""
    pass


class APIClient:
    """
    Client pour consommer les API REST
    """

    def __init__(self, user_id=None, token=None):
        self.user_id = user_id
        self.token = token
        self.headers = {
            'Content-Type': 'application/json'
        }

        if user_id:
            self.headers['X-User-Id'] = str(user_id)

        if token:
            self.headers['Authorization'] = f'Bearer {token}'

    def _get_headers(self, content_type=None):
        """Retourne les headers avec le bon Content-Type si nécessaire"""
        headers = self.headers.copy()
        if content_type:
            headers['Content-Type'] = content_type
        return headers

    @handle_api_errors
    def _make_request(self, method, endpoint, data=None, files=None, params=None):
        url = f"{API_BASE_URL}{endpoint}"

        logger.debug(f"Envoi d'une requête {method} à {url}")

        # Si nous avons des fichiers, nous ne devons pas inclure Content-Type
        headers = self.headers.copy()
        if files:
            headers = {k: v for k, v in headers.items() if k != 'Content-Type'}

        response = requests.request(
            method,
            url,
            json=data if method.lower() in ['post', 'put', 'patch'] and not files else None,
            data=data if method.lower() in ['post', 'put', 'patch'] and files else None,
            headers=headers,
            params=params,
            files=files,
            timeout=10  # Timeout de 10 secondes
        )

        logger.debug(f"Réponse: {response.status_code}")

        # Vérifier les codes d'erreur et lever des exceptions appropriées
        if response.status_code >= 400:
            error_msg = f"Erreur HTTP {response.status_code}"
            if response.text:
                try:
                    error_details = response.json()
                    error_msg = f"{error_msg}: {json.dumps(error_details)}"
                except json.JSONDecodeError:
                    error_msg = f"{error_msg}: {response.text}"

            logger.error(error_msg)
            notify_error(error_msg, endpoint, f"Status code: {response.status_code}", data)

            if response.status_code == 401:
                raise APIException("Non autorisé. Veuillez vous reconnecter.")
            elif response.status_code == 403:
                raise APIException("Accès interdit. Vous n'avez pas les permissions nécessaires.")
            elif response.status_code == 404:
                raise APIException("Ressource non trouvée.")
            elif response.status_code >= 500:
                raise APIException("Erreur serveur. Veuillez réessayer plus tard.")
            else:
                raise APIException(f"Erreur d'API: {error_msg}")

        # Analyser la réponse JSON si applicable
        if response.content and response.headers.get('Content-Type', '').startswith('application/json'):
            try:
                return response.json()
            except json.JSONDecodeError as e:
                error_msg = f"Erreur lors du décodage de la réponse JSON: {str(e)}"
                logger.error(error_msg)
                notify_error(error_msg, endpoint, traceback.format_exc(), data)
                raise APIException(error_msg)

        # Si c'est une image ou un autre type de contenu binaire
        elif response.content and response.headers.get('Content-Type', '').startswith('image/'):
            return response.content

        # Si c'est une réponse vide mais réussie (204 No Content)
        elif response.status_code == 204:
            return {'status': 'success'}

        # Sinon, retourner la réponse textuelle
        return response.text

    # Méthodes pour les utilisateurs
    @handle_api_errors
    def login(self, email, password):
        """Connexion utilisateur"""
        data = {
            'email': email,
            'mot_de_passe': password  # Utilisation du nom de champ exact comme dans l'entité Utilisateur
        }
        return self._make_request('POST', '/utilisateurs/login', data=data)

    @handle_api_errors
    def signup(self, nom, prenom, email, password, role='EMPLOYE'):
        """Inscription utilisateur"""
        data = {
            'nom': nom,
            'prenom': prenom,
            'email': email,
            'mot_de_passe': password,
            'role': role
        }
        return self._make_request('POST', '/utilisateurs/signup', data=data)

    @handle_api_errors
    def get_all_users(self):
        """Récupérer tous les utilisateurs"""
        return self._make_request('GET', '/utilisateurs')

    @handle_api_errors
    def get_user(self, user_id):
        """Récupérer un utilisateur par ID"""
        return self._make_request('GET', f'/utilisateurs/{user_id}')

    @handle_api_errors
    def update_user(self, user_id, user_data):
        """Mettre à jour un utilisateur"""
        return self._make_request('PUT', f'/utilisateurs/{user_id}', data=user_data)

    @handle_api_errors
    def delete_user(self, user_id):
        """Supprimer un utilisateur"""
        return self._make_request('DELETE', f'/utilisateurs/{user_id}')

    @handle_api_errors
    def check_email_exists(self, email):
        """Vérifier si un email existe déjà"""
        return self._make_request('GET', '/utilisateurs/email-existe', params={'email': email})

    # Méthodes pour les produits
    @handle_api_errors
    def get_all_products(self):
        """Récupérer tous les produits"""
        return self._make_request('GET', '/produits')

    @handle_api_errors
    def get_product(self, product_id):
        """Récupérer un produit par ID"""
        return self._make_request('GET', f'/produits/{product_id}')

    @handle_api_errors
    def get_product_image(self, product_id):
        """Récupérer l'image d'un produit"""
        return self._make_request('GET', f'/produits/{product_id}/image')

    @handle_api_errors
    def get_products_by_category(self, category_id):
        """Récupérer les produits par catégorie"""
        return self._make_request('GET', f'/produits/categorie/{category_id}')

    @handle_api_errors
    def get_products_by_status(self, status):
        """Récupérer les produits par statut"""
        return self._make_request('GET', f'/produits/statut/{status}')

    @handle_api_errors
    def search_products(self, name):
        """Rechercher des produits par nom"""
        return self._make_request('GET', '/produits/search', params={'nom': name})

    @handle_api_errors
    def create_product(self, nom, description, prix, categorie_id, image_file=None):
        """
        Créer un nouveau produit

        Args:
            nom: Nom du produit
            description: Description du produit
            prix: Prix du produit
            categorie_id: ID de la catégorie
            image_file: Fichier image à télécharger (optionnel)
        """
        # Données de base du produit
        data = {
            'nom': nom,
            'description': description,
            'prix': str(prix),
            'categorieId': str(categorie_id)
        }

        # Configuration des fichiers pour l'upload d'image
        files = None
        if image_file:
            files = {'image': image_file}

        return self._make_request('POST', '/produits', data=data, files=files)

    @handle_api_errors
    def update_product(self, product_id, nom, description, prix, categorie_id, image_file=None, remove_image=False):
        """
        Mettre à jour un produit

        Args:
            product_id: ID du produit à mettre à jour
            nom: Nouveau nom du produit
            description: Nouvelle description
            prix: Nouveau prix
            categorie_id: Nouvelle catégorie
            image_file: Nouveau fichier image (optionnel)
            remove_image: True pour supprimer l'image existante sans la remplacer
        """
        # Données de base du produit
        data = {
            'nom': nom,
            'description': description,
            'prix': str(prix),
            'categorieId': str(categorie_id)
        }

        # Ajouter un indicateur si l'image doit être supprimée
        if remove_image:
            data['removeImage'] = 'true'

        # Configuration des fichiers pour l'upload d'image
        files = None
        if image_file:
            files = {'image': image_file}

        return self._make_request('PUT', f'/produits/{product_id}', data=data, files=files)

    @handle_api_errors
    def update_product_status(self, product_id, status):
        """Mettre à jour le statut d'un produit"""
        return self._make_request('PATCH', f'/produits/{product_id}/statut', params={'statut': status})

    @handle_api_errors
    def delete_product(self, product_id):
        """Supprimer un produit"""
        return self._make_request('DELETE', f'/produits/{product_id}')

    @handle_api_errors
    def check_product_name_exists(self, nom):
        """Vérifier si un nom de produit existe déjà"""
        return self._make_request('GET', '/produits/check-nom', params={'nom': nom})

    # Méthodes pour les catégories
    @handle_api_errors
    def get_all_categories(self):
        """Récupérer toutes les catégories"""
        return self._make_request('GET', '/categories')

    @handle_api_errors
    def get_category(self, category_id):
        """Récupérer une catégorie par ID"""
        return self._make_request('GET', f'/categories/{category_id}')

    @handle_api_errors
    def create_category(self, nom):
        """Créer une nouvelle catégorie"""
        data = {'nom': nom}
        return self._make_request('POST', '/categories', data=data)

    @handle_api_errors
    def update_category(self, category_id, nom):
        """Mettre à jour une catégorie"""
        data = {'nom': nom, 'id': category_id}
        return self._make_request('PUT', f'/categories/{category_id}', data=data)

    @handle_api_errors
    def delete_category(self, category_id):
        """Supprimer une catégorie"""
        return self._make_request('DELETE', f'/categories/{category_id}')

    @handle_api_errors
    def check_category_name_exists(self, nom):
        """Vérifier si un nom de catégorie existe déjà"""
        return self._make_request('GET', '/categories/check-nom', params={'nom': nom})

    @handle_api_errors
    def update_user_status(self, user_id, status):
        """
        Met à jour le statut d'un utilisateur en utilisant l'endpoint PUT existant
        """
        # Récupérer d'abord les informations actuelles de l'utilisateur
        user = self.get_user(user_id)

        if not user:
            raise APIException("Utilisateur non trouvé")

        # Mettre à jour le statut
        user['statut'] = status

        # Envoyer la mise à jour
        return self.update_user(user_id, user)

    @handle_api_errors
    def login_and_activate(self, email, password, user_id):
        """
        Se connecte avec les identifiants fournis puis active le compte utilisateur
        """
        # 1. Se connecter avec les identifiants
        login_response = self.login(email, password)

        if not isinstance(login_response, dict) or 'id' not in login_response:
            raise APIException("Échec de la connexion lors de la vérification du compte")

        # 2. Récupérer l'utilisateur avec les informations complètes
        user_data = login_response

        # 3. Mettre à jour le statut et le flag de vérification
        user_data['statut'] = 'A'  # Actif
        user_data['estVerifie'] = True

        # 4. Utiliser l'ID connecté pour l'authentification
        auth_client = APIClient(user_id=login_response['id'])

        # 5. Mettre à jour l'utilisateur
        response = auth_client.update_user(user_id, user_data)

        if not isinstance(response, dict) or 'id' not in response:
            raise APIException("Échec de la mise à jour du statut utilisateur")

        return response

    @handle_api_errors
    def verify_user(self, user_id, email):
        """
        Vérifie le compte d'un utilisateur en utilisant le nouvel endpoint sécurisé
        """
        data = {
            'email': email
        }
        return self._make_request('PUT', f'/utilisateurs/verify/{user_id}', data=data)
