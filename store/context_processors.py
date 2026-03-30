import base64

from .models import Wishlist, Cart

def nav_counts(request):
    wishlist_count = 0
    cart_count = 0
    user_avatar_data_uri = ""
    user_avatar_initial = "U"

    if request.user.is_authenticated:
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        cart_count = Cart.objects.filter(user=request.user).count()
        user_avatar_initial = (request.user.username[:1] or "U").upper()

        profile_image = getattr(request.user, "profile_image", None)
        if profile_image:
            if isinstance(profile_image, memoryview):
                profile_image = profile_image.tobytes()
            user_avatar_data_uri = f"data:image/png;base64,{base64.b64encode(profile_image).decode('utf-8')}"

    return {
        'wishlist_count': wishlist_count,
        'cart_count': cart_count,
        'user_avatar_data_uri': user_avatar_data_uri,
        'user_avatar_initial': user_avatar_initial,
    }
