import random
import string
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .api_client import APIClient, APIException
import logging

logger = logging.getLogger(__name__)


def generate_verification_code(length=6):
    """Génère un code de vérification aléatoire"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def send_verification_email(email, code, user_name):
    """Envoie un email avec le code de vérification"""
    subject = f"Vérification de votre compte - {settings.SITE_NAME}"

    # Préparation du contenu HTML de l'email
    html_message = render_to_string('emails/verification_code.html', {
        'code': code,
        'user_name': user_name,
        'site_name': settings.SITE_NAME
    })

    # Message texte simple
    plain_message = f"""
    Bonjour {user_name},

    Merci de vous être inscrit sur {settings.SITE_NAME}.

    Votre code de vérification est: {code}

    Ce code est valable pendant 30 minutes.

    L'équipe {settings.SITE_NAME}
    """

    # Envoi de l'email
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email à {email}: {str(e)}")
        return False


def login_view(request):
    """Vue pour la page de connexion"""
    # Si l'utilisateur est déjà connecté, le rediriger vers la page d'accueil
    if request.session.get('user_role') in ['SUPER_ADMIN', 'GERANT']:
        return redirect('dashboard')

    elif request.session.get('user_role') in ['EMPLOYE']:
        return redirect('dashboard_employe')

    next_url = request.GET.get('next', reverse('dashboard'))


    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not email or not password:
            messages.error(request, "Veuillez saisir votre email et votre mot de passe.")
            return render(request, 'login.html', {'next': next_url})

        try:
            # Appel à l'API pour la connexion
            client = APIClient()
            response = client.login(email, password)

            # Vérifier si la connexion a réussi
            if isinstance(response, dict) and 'id' in response:
                # Vérifier si le compte est actif
                if response.get('statut') != 'A':
                    messages.error(request,
                                   "Votre compte n'est pas encore activé. "
                                   "Veuillez vérifier votre email et activer votre compte."
                                   )
                    # Stocker l'ID utilisateur pour la vérification
                    request.session['verification_user_id'] = response['id']
                    request.session['verification_email'] = response['email']
                    request.session['verification_name'] = f"{response.get('prenom', '')} {response.get('nom', '')}"

                    # Générer un nouveau code de vérification
                    verification_code = generate_verification_code()
                    request.session['verification_code'] = verification_code

                    # Envoyer l'email avec le code
                    success = send_verification_email(
                        response['email'],
                        verification_code,
                        f"{response.get('prenom', '')} {response.get('nom', '')}"
                    )

                    if success:
                        messages.info(request, "Un code de vérification a été envoyé à votre adresse email.")
                    else:
                        messages.warning(request,
                                         "Nous n'avons pas pu envoyer le code de vérification. "
                                         "Veuillez contacter l'administrateur."
                                         )

                    return redirect('verify_account')

                # Si le compte est actif, stocker les informations de l'utilisateur dans la session
                request.session['user_id'] = response['id']
                request.session['user_role'] = response.get('role', 'EMPLOYE')
                request.session['user_name'] = f"{response.get('prenom', '')} {response.get('nom', '')}"
                request.session['user_email'] = response.get('email', '')

                if request.session.get('user_role') in ['SUPER_ADMIN', 'GERANT']:
                    next_url = request.GET.get('next', reverse('dashboard'))
                else:
                    next_url = request.GET.get('next', reverse('dashboard_employe'))


                # Journaliser la connexion réussie
                logger.info(f"Connexion réussie pour l'utilisateur {email} (ID: {response['id']})")

                # Rediriger vers la page demandée
                return redirect(next_url)
            else:
                # La réponse n'a pas le format attendu
                logger.warning(f"Format de réponse inattendu lors de la connexion: {response}")
                messages.error(request, "Une erreur est survenue lors de la connexion. Veuillez réessayer.")

        except APIException as e:
            # Gestion des erreurs d'API
            logger.error(f"Erreur lors de la connexion pour {email}: {str(e)}")
            messages.error(request, f"Erreur de connexion: {str(e)}")

        except Exception as e:
            # Gestion des autres erreurs
            logger.error(f"Erreur inattendue lors de la connexion: {str(e)}")
            messages.error(request, "Une erreur inattendue s'est produite. Veuillez réessayer ultérieurement.")

    return render(request, 'login.html', {'next': next_url})


def logout_view(request):
    """Vue pour la déconnexion"""
    # Récupérer les informations avant de les supprimer pour le logging
    user_id = request.session.get('user_id')
    user_email = request.session.get('user_email')

    # Nettoyer la session
    if 'user_id' in request.session:
        del request.session['user_id']
    if 'user_role' in request.session:
        del request.session['user_role']
    if 'user_name' in request.session:
        del request.session['user_name']
    if 'user_email' in request.session:
        del request.session['user_email']

    # Journaliser la déconnexion
    if user_id:
        logger.info(f"Déconnexion de l'utilisateur {user_email} (ID: {user_id})")

    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('login')


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

            # Inscription de l'utilisateur avec statut 'D' (par défaut, en attente de validation)
            response = client.signup(nom, prenom, email, password)

            # Vérifier si l'inscription a réussi
            if isinstance(response, dict) and 'id' in response:
                user_id = response['id']

                # Générer un code de vérification
                verification_code = generate_verification_code()

                # Stocker le code et l'ID utilisateur dans la session
                request.session['verification_user_id'] = user_id
                request.session['verification_code'] = verification_code
                request.session['verification_email'] = email
                request.session['verification_name'] = f"{prenom} {nom}"

                # Envoyer l'email avec le code
                success = send_verification_email(email, verification_code, f"{prenom} {nom}")

                if success:
                    logger.info(f"Email de vérification envoyé à {email}")
                    messages.success(request,
                                     "Inscription réussie ! Un code de vérification a été envoyé à votre adresse email."
                                     )
                else:
                    logger.error(f"Erreur lors de l'envoi de l'email de vérification à {email}")
                    messages.warning(request,
                                     "Votre compte a été créé, mais nous n'avons pas pu envoyer l'email de vérification. "
                                     "Veuillez contacter l'administrateur."
                                     )

                # Rediriger vers la page de vérification
                return redirect('verify_account')
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


def verify_account_view(request):
    """Vue pour la vérification du compte avec le code envoyé par email"""
    # Récupérer les données de session
    user_id = request.session.get('verification_user_id')
    stored_code = request.session.get('verification_code')
    email = request.session.get('verification_email')
    user_name = request.session.get('verification_name')

    # Si les données de vérification ne sont pas présentes, rediriger vers l'inscription
    if not all([user_id, stored_code, email]):
        messages.error(request, "Aucune vérification en attente. Veuillez vous inscrire.")
        return redirect('signup')

    if request.method == 'POST':
        # Récupérer le code saisi
        verification_code = request.POST.get('verification_code')

        if not verification_code:
            messages.error(request, "Veuillez saisir le code de vérification.")
            return render(request, 'verify_account.html', {'email': email})

        # Vérifier si le code correspond
        if verification_code == stored_code:
            try:
                # Créer le client API
                client = APIClient(user_id=user_id)  # Utilisation de l'ID pour l'authentification

                response = client.verify_user(user_id, email)

                # Vérifier si la mise à jour a réussi
                if isinstance(response, dict) and 'id' in response:
                    # Nettoyer les données de vérification de la session
                    if 'verification_user_id' in request.session:
                        del request.session['verification_user_id']
                    if 'verification_code' in request.session:
                        del request.session['verification_code']
                    if 'verification_email' in request.session:
                        del request.session['verification_email']
                    if 'verification_name' in request.session:
                        del request.session['verification_name']

                    # Journaliser la vérification réussie
                    logger.info(f"Vérification réussie pour l'utilisateur {email} (ID: {user_id})")

                    messages.success(request,
                                     "Votre compte a été vérifié avec succès. "
                                     "Vous pouvez maintenant vous connecter."
                                     )
                    return redirect('login')
                else:
                    # La réponse n'a pas le format attendu
                    logger.warning(f"Format de réponse inattendu lors de la vérification: {response}")
                    messages.error(request,
                                   "Une erreur est survenue lors de la vérification. "
                                   "Veuillez réessayer ou contacter l'administrateur."
                                   )

            except APIException as e:
                # Gestion des erreurs d'API
                logger.error(f"Erreur lors de la vérification pour {email}: {str(e)}")
                messages.error(request, f"Erreur de vérification: {str(e)}")

            except Exception as e:
                # Gestion des autres erreurs
                logger.error(f"Erreur inattendue lors de la vérification: {str(e)}")
                messages.error(request, "Une erreur inattendue s'est produite. Veuillez réessayer ultérieurement.")
        else:
            messages.error(request, "Code de vérification incorrect. Veuillez réessayer.")

    return render(request, 'verify_account.html', {'email': email})


def resend_verification_code(request):
    """Vue pour renvoyer le code de vérification"""
    # Récupérer les données de session
    user_id = request.session.get('verification_user_id')
    email = request.session.get('verification_email')
    user_name = request.session.get('verification_name')

    # Si les données de vérification ne sont pas présentes, rediriger vers l'inscription
    if not all([user_id, email, user_name]):
        messages.error(request, "Aucune vérification en attente. Veuillez vous inscrire.")
        return redirect('signup')

    # Générer un nouveau code de vérification
    verification_code = generate_verification_code()

    # Mettre à jour le code dans la session
    request.session['verification_code'] = verification_code

    # Envoyer l'email avec le nouveau code
    success = send_verification_email(email, verification_code, user_name)

    if success:
        logger.info(f"Nouveau code de vérification envoyé à {email}")
        messages.success(request, f"Un nouveau code de vérification a été envoyé à {email}.")
    else:
        logger.error(f"Erreur lors de l'envoi du nouveau code de vérification à {email}")
        messages.error(request,
                       "Nous n'avons pas pu envoyer le nouveau code de vérification. "
                       "Veuillez réessayer ou contacter l'administrateur."
                       )

    return redirect('verify_account')