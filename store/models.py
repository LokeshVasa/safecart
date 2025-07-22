from django.db import models

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('men', 'Men'),
        ('women', 'Women'),
        ('kids', 'Kids'),
        ('electronics', 'Electronics'),
        ('furniture', 'Furniture'),
        ('sportswear', 'Sportswear'),
        ('footwear', 'Footwear'),
    ]
    
    name = models.CharField(max_length=100)
    category = models.CharField(
    max_length=20,
    choices=CATEGORY_CHOICES,
    default='men'  # Default category
)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.category})"
