class ProfileUpdateError(Exception):
    pass


def remove_profile_photo(user):
    user.profile_image = None
    user.save(update_fields=["profile_image"])


def update_profile_photo(user, uploaded_photo):
    if not uploaded_photo:
        raise ProfileUpdateError("Please choose an image before uploading.")

    if not uploaded_photo.content_type or not uploaded_photo.content_type.startswith("image/"):
        raise ProfileUpdateError("Only image files are allowed for profile photos.")

    user.profile_image = uploaded_photo.read()
    user.save(update_fields=["profile_image"])
