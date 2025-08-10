from .models import Wishlist, Cart

def nav_counts(request):
    wishlist_count = 0
    cart_count = 0

    if request.user.is_authenticated:
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        cart_count = Cart.objects.filter(user=request.user).count()

    return {
        'wishlist_count': wishlist_count,
        'cart_count': cart_count
    }
