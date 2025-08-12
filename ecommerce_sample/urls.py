from django.contrib import admin
from django.urls import path
from store.views import product, cart, clear_data, profile, home, yourorders
from store import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', views.RegisterView, name='register'),
    path('login/', views.LoginView, name='login'),
    path('logout/', views.LogoutView, name='logout'),
    path('forgot-password/', views.ForgotPassword, name='forgot-password'),
    path('password-reset-sent/<str:reset_id>/', views.PasswordResetSent, name='password-reset-sent'),
    path('reset-password/<str:reset_id>/', views.ResetPassword, name='reset-password'),
    path("", views.home),
    path("home", views.home, name='home'),
    path("cart", views.cart),
    path("clear_data", views.clear_data),
    path("profile", views.profile),
    path("wishlist", views.wishlist_view, name='wishlist'),  
    path("yourorders", views.yourorders),
    path("product", views.product),
    path("add-to-cart/", views.add_to_cart, name='add-to-cart'),
    path("add-to-wishlist/", views.add_to_wishlist, name='add-to-wishlist'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/move-to-wishlist/<int:product_id>/', views.move_to_wishlist, name='move_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),path('wishlist/move-to-cart/<int:product_id>/', views.move_to_cart, name='move_to_cart'),

]

# Serve media in development
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
