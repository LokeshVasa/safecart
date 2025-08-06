from django.db import models
import uuid

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

    class Meta:
        db_table = 'products'  #table name


class Category(models.Model):
    category = models.CharField(max_length=100)
    heading = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='categories/')

    def __str__(self):
        return self.category

    class Meta:
        db_table = 'categories'  #table name
        
from django.contrib.auth.models import User
User._meta.get_field('email')._unique = True

class PasswordReset(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reset_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_when = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Password reset for {self.user.username} at {self.created_when}"
        

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product= models.ForeignKey(Product, on_delete=models.CASCADE)
    created_when= models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.product}"

    class Meta:
        db_table = 'cart'

class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product= models.ForeignKey(Product, on_delete=models.CASCADE)
    created_when= models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.product}"

    class Meta:
        db_table = 'wishlist'

       