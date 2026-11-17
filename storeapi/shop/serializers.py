from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Category, Order, OrderItem, Product

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff"]


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "description", "product_count"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "description", "price", "stock",
            "is_active", "category", "category_name", "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    product_name = serializers.CharField(source="product.name", read_only=True)
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = OrderItem
        fields = ["product", "product_name", "quantity", "unit_price"]
        read_only_fields = ["unit_price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ["id", "status", "total", "created_at", "items"]
        read_only_fields = ["status", "total", "created_at"]

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("An order needs at least one item.")
        ids = [i["product"].pk for i in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each product may appear only once.")
        return items

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        # Lock the product rows so two simultaneous orders can't oversell stock.
        products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(
                pk__in=[i["product"].pk for i in items_data]
            )
        }

        order = Order.objects.create(**validated_data)
        total = 0
        for item in items_data:
            product = products[item["product"].pk]
            qty = item["quantity"]
            if product.stock < qty:
                raise serializers.ValidationError(
                    {"items": f"Not enough stock for '{product.name}' (available: {product.stock})."}
                )
            product.stock -= qty
            product.save(update_fields=["stock"])
            OrderItem.objects.create(
                order=order, product=product, quantity=qty, unit_price=product.price
            )
            total += product.price * qty

        order.total = total
        order.save(update_fields=["total"])
        return order
