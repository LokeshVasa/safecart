from django.contrib import admin
from django.urls import path
from store.views import product, cart, clear_data, profile, home, yourorders
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
]

# Serve media in development
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
