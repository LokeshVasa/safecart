from django.contrib import admin
from django.urls import path, include
from store.views import product, cart, clear_data, login_user, profile, signup, wishlist, home, yourorders
from django.contrib import messages
from store import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', views.RegisterView, name='register'),
    path('login/', views.LoginView, name='login'),
    path('logout/', views.LogoutView, name='logout'),
    path('forgot-password/', views.ForgotPassword, name='forgot-password'),
    path('password-reset-sent/<str:reset_id>/', views.PasswordResetSent, name='password-reset-sent'),
    path('reset-password/<str:reset_id>/', views.ResetPassword, name='reset-password'),
    # path('', include('django.contrib.auth.urls')),  # includes login, logout, password reset, etc.
    # Custom views
    path("", home),
    path("home", home, name='home'),
    path("cart", cart),
    path("clear_data", clear_data),
    path("profile", profile),
    path("wishlist", wishlist),
    path("yourorders", yourorders),
    path("product", product),
]

# Serve media in development
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
