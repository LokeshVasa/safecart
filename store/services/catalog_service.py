from pathlib import Path

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.templatetags.static import static

from store.models import Category, Product


def build_product_page_context(category_slug):
    normalized_category = (category_slug or "men").strip().lower()
    category_object = get_object_or_404(Category, category__iexact=normalized_category)
    products = Product.objects.filter(category__iexact=normalized_category)
    return {
        "products": products,
        "heading": category_object.heading,
        "description": category_object.description,
        "category": category_object.category,
    }


def build_home_context():
    categories = list(Category.objects.all())
    featured_products = Product.objects.order_by("-created_at")[:8]
    hero_categories = categories[:3]
    static_images_dir = Path(settings.BASE_DIR) / "static" / "images"
    hero_slides = []

    for category in hero_categories:
        category_slug = category.category.strip().lower().replace(" ", "-")
        static_image_src = None

        for extension in ("webp", "jpg", "jpeg", "png"):
            candidate_name = f"hero-{category_slug}.{extension}"
            candidate_path = static_images_dir / candidate_name
            if candidate_path.exists():
                static_image_src = static(f"images/{candidate_name}")
                break

        hero_slides.append({
            "category": category.category,
            "category_param": category.category.strip().lower(),
            "heading": category.heading,
            "description": category.description,
            "image_src": static_image_src or category.image.url,
        })

    return {
        "categories": categories,
        "hero_categories": hero_slides,
        "featured_products": featured_products,
    }
