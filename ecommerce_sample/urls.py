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
    path("cart", views.cart,name='cart'),
    path("clear_data", views.clear_data),
    path("profile", views.profile, name="profile"),
    path("wishlist", views.wishlist_view, name='wishlist'),  
    path("yourorders", views.yourorders, name="yourorders"),
    path("product", views.product),
    path("add-to-cart/", views.add_to_cart, name='add-to-cart'),
    path("add-to-wishlist/", views.add_to_wishlist, name='add-to-wishlist'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/move-to-wishlist/<int:product_id>/', views.move_to_wishlist, name='move_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/move-to-cart/<int:product_id>/', views.move_to_cart, name='move_to_cart'),
    path("save-address/", views.save_address, name="save_address"),
    path("proceed-to-checkout/", views.proceed_to_checkout, name="proceed_to_checkout"),
    path("cart/change/<int:product_id>/", views.change_quantity, name="change_quantity"),
    path('sellerorders/', views.sellerorders, name='sellerorders'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('redirect-dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/admin/promote/<int:user_id>/', views.make_delivery_agent, name='promote_user'),
    path('delivery/dashboard/', views.delivery_dashboard, name='delivery_dashboard'),
    path('delivery/order/', views.delivery_order_detail, name='delivery_order_detail'),
    path('delivery/mark-delivered/<int:order_id>/', views.mark_order_delivered, name='mark_order_delivered'), 
    path('api/get_order_by_token/', views.get_order_by_token, name='get_order_by_token'),
]

# Serve media in development
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)