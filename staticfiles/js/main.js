// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // Variables
    const menuToggle = document.getElementById('menuToggle');
    const mobileMenu = document.getElementById('mobileMenu');
    const categoryPills = document.querySelectorAll('.category-pill');
    const productCards = document.querySelectorAll('.product-card');
    const searchInput = document.getElementById('searchInput');
    const searchButton = document.getElementById('searchButton');
    const skeletonLoader = document.getElementById('skeletonLoader');
    const productsGrid = document.getElementById('productsGrid');
    const loadMoreButton = document.getElementById('loadMoreButton');

    // Fonction pour afficher/masquer le menu mobile
    if (menuToggle && mobileMenu) {
        menuToggle.addEventListener('click', function() {
            mobileMenu.style.display = mobileMenu.style.display === 'block' ? 'none' : 'block';
        });
    }

    // Fonction pour filtrer les produits par catégorie
    if (categoryPills.length > 0 && productCards.length > 0) {
        categoryPills.forEach(pill => {
            pill.addEventListener('click', function() {
                // Retirer la classe active de toutes les pills
                categoryPills.forEach(p => p.classList.remove('active'));

                // Ajouter la classe active à la pill cliquée
                this.classList.add('active');

                const selectedCategory = this.dataset.category;

                // Afficher tous les produits si "all" est sélectionné
                if (selectedCategory === 'all') {
                    productCards.forEach(card => {
                        card.style.display = 'block';
                    });
                } else {
                    // Sinon, filtrer par catégorie
                    productCards.forEach(card => {
                        if (card.dataset.category === selectedCategory) {
                            card.style.display = 'block';
                        } else {
                            card.style.display = 'none';
                        }
                    });
                }
            });
        });
    }

    // Fonction pour rechercher des produits
    if (searchInput && searchButton) {
        searchButton.addEventListener('click', searchProducts);
        searchInput.addEventListener('keyup', function(event) {
            if (event.key === 'Enter') {
                searchProducts();
            }
        });

        function searchProducts() {
            const searchTerm = searchInput.value.toLowerCase().trim();

            if (searchTerm === '') {
                productCards.forEach(card => {
                    card.style.display = 'block';
                });
                return;
            }

            productCards.forEach(card => {
                const productTitle = card.querySelector('.product-title').textContent.toLowerCase();

                if (productTitle.includes(searchTerm)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
    }

    // Simulation de chargement des produits
    if (skeletonLoader && productsGrid) {
        // Cacher le skeleton loader après 1 seconde
        setTimeout(() => {
            skeletonLoader.style.display = 'none';
            productsGrid.style.display = 'grid';
        }, 1000);
    }

    // Fonctionnalités pour les boutons "Ajouter au panier"
    const addToCartButtons = document.querySelectorAll('.add-to-cart-button');
    const cartCount = document.querySelector('.cart-count');
    let cartItems = 0;

    if (addToCartButtons.length > 0 && cartCount) {
        addToCartButtons.forEach(button => {
            button.addEventListener('click', function() {
                cartItems++;
                cartCount.textContent = cartItems;

                // Animation du bouton
                button.classList.add('added');
                button.textContent = 'Ajouté !';

                setTimeout(() => {
                    button.classList.remove('added');
                    button.innerHTML = '<i class="fas fa-shopping-cart"></i> Ajouter au panier';
                }, 1500);

                // Animation de l'icône du panier
                const cartIcon = document.querySelector('.nav-icon .fa-shopping-cart');
                if (cartIcon) {
                    cartIcon.classList.add('pulse');
                    setTimeout(() => {
                        cartIcon.classList.remove('pulse');
                    }, 1000);
                }
            });
        });
    }

    // Fonction pour charger plus de produits
    if (loadMoreButton) {
        loadMoreButton.addEventListener('click', function() {
            // Simuler le chargement de plus de produits
            loadMoreButton.textContent = 'Chargement...';

            setTimeout(() => {
                // Exemple de produits à ajouter
                const newProducts = [
                    { name: 'Produit Supplémentaire 1', price: '99,99 €', category: '1' },
                    { name: 'Produit Supplémentaire 2', price: '129,99 €', category: '2' },
                    { name: 'Produit Supplémentaire 3', price: '79,99 €', category: '3' },
                    { name: 'Produit Supplémentaire 4', price: '149,99 €', category: '1' }
                ];

                // Ajouter les nouveaux produits à la grille
                newProducts.forEach(product => {
                    const productHTML = `
                        <div class="product-card" data-category="${product.category}">
                            <div class="product-image">
                                <img src="/static/images/placeholder.jpg" alt="${product.name}">
                            </div>
                            <h3 class="product-title">${product.name}</h3>
                            <div class="product-rating">
                                <i class="fas fa-star"></i>
                                <i class="fas fa-star"></i>
                                <i class="fas fa-star"></i>
                                <i class="fas fa-star"></i>
                                <i class="far fa-star"></i>
                            </div>
                            <div class="product-price">
                                <span>${product.price}</span>
                            </div>
                            <button class="add-to-cart-button">
                                <i class="fas fa-shopping-cart"></i> Ajouter au panier
                            </button>
                        </div>
                    `;

                    productsGrid.insertAdjacentHTML('beforeend', productHTML);
                });

                // Mettre à jour les événements pour les nouveaux boutons
                const newAddToCartButtons = productsGrid.querySelectorAll('.add-to-cart-button:not(.has-event)');
                newAddToCartButtons.forEach(button => {
                    button.classList.add('has-event');
                    button.addEventListener('click', function() {
                        cartItems++;
                        cartCount.textContent = cartItems;

                        // Animation du bouton
                        button.classList.add('added');
                        button.textContent = 'Ajouté !';

                        setTimeout(() => {
                            button.classList.remove('added');
                            button.innerHTML = '<i class="fas fa-shopping-cart"></i> Ajouter au panier';
                        }, 1500);
                    });
                });

                loadMoreButton.textContent = 'Voir plus de produits';
            }, 1500);
        });
    }

    // Remplir le carousel de nouveaux produits
    const newProductsCarousel = document.getElementById('newProductsCarousel');
    if (newProductsCarousel) {
        const newProductsData = [
            { name: 'Nouveau Produit 1', price: '129,99 €', image: 'placeholder.jpg' },
            { name: 'Nouveau Produit 2', price: '79,99 €', image: 'placeholder.jpg' },
            { name: 'Nouveau Produit 3', price: '149,99 €', image: 'placeholder.jpg' },
            { name: 'Nouveau Produit 4', price: '89,99 €', image: 'placeholder.jpg' },
            { name: 'Nouveau Produit 5', price: '199,99 €', image: 'placeholder.jpg' }
        ];

        newProductsData.forEach(product => {
            const productHTML = `
                <div class="product-card">
                    <span class="product-badge sale">Nouveau</span>
                    <div class="product-image">
                        <img src="/static/images/${product.image}" alt="${product.name}">
                    </div>
                    <h3 class="product-title">${product.name}</h3>
                    <div class="product-rating">
                        <i class="fas fa-star"></i>
                        <i class="fas fa-star"></i>
                        <i class="fas fa-star"></i>
                        <i class="fas fa-star"></i>
                        <i class="far fa-star"></i>
                    </div>
                    <div class="product-price">
                        <span>${product.price}</span>
                    </div>
                    <button class="add-to-cart-button">
                        <i class="fas fa-shopping-cart"></i> Ajouter au panier
                    </button>
                </div>
            `;

            newProductsCarousel.insertAdjacentHTML('beforeend', productHTML);
        });
    }

    // Animations au défilement
    const animateOnScroll = () => {
        const elements = document.querySelectorAll('.section-title, .product-card, .testimonial');

        elements.forEach(element => {
            const elementPosition = element.getBoundingClientRect().top;
            const screenPosition = window.innerHeight / 1.2;

            if (elementPosition < screenPosition) {
                element.classList.add('fade-in');
            }
        });
    };

    // Ajouter la classe pour le CSS
    document.head.insertAdjacentHTML('beforeend', `
        <style>
            .section-title, .product-card, .testimonial {
                opacity: 0;
                transform: translateY(20px);
                transition: opacity 0.6s ease, transform 0.6s ease;
            }
            
            .fade-in {
                opacity: 1;
                transform: translateY(0);
            }
            
            .add-to-cart-button.added {
                background-color: #4CAF50;
            }
            
            .pulse {
                animation: pulse-animation 1s ease;
            }
            
            @keyframes pulse-animation {
                0% { transform: scale(1); }
                50% { transform: scale(1.2); }
                100% { transform: scale(1); }
            }
        </style>
    `);

    window.addEventListener('scroll', animateOnScroll);
    animateOnScroll(); // Lancer une fois au chargement
});