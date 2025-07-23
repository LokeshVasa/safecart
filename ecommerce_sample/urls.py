"""
URL configuration for ecommerce_sample project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path 
from store.views import product, cart, clear_data,login, profile, signup, wishlist, home,yourorders

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", home ),
    path("home", home ),
    path('cart', cart), 
    #path('men', men), 
    #path('women', women), 
    #path('kids', kids), 
    path('clear_data', clear_data), 
    #path('electronics',electronics ), 
    #path('furniture', furniture), 
    path('login', login), 
    path('profile', profile), 
    path('signup', signup), 
    #path('sportswear', sportswear), 
    path('wishlist', wishlist), 
    path('yourorders', yourorders), 
    path('product',product),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

