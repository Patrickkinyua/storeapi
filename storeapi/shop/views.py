from django.db import transaction
from django.db.models import Count, F, Sum
from django.db.models.deletion import ProtectedError
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Order, Product
from .permissions import IsAdminOrReadOnly
from .serializers import (
    CategorySerializer, OrderSerializer, ProductSerializer,
    RegisterSerializer, UserSerializer,
)


# ---------- Auth ----------

class RegisterView(generics.CreateAPIView):
    """Create an account and get an API token back."""
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"user": UserSerializer(user).data, "token": token.key},
            status=status.HTTP_201_CREATED,
        )


class MeView(generics.RetrieveAPIView):
    """The currently authenticated user."""
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


# ---------- Catalogue ----------

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ["name"]

    def get_queryset(self):
        return Category.objects.annotate(product_count=Count("products"))

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Category still has products. Move or delete them first."},
                status=status.HTTP_409_CONFLICT,
            )


class ProductFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    in_stock = filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ["category", "is_active"]

    def filter_in_stock(self, queryset, name, value):
        return queryset.filter(stock__gt=0) if value else queryset.filter(stock=0)


class ProductViewSet(viewsets.ModelViewSet):
    """
    Filters:  ?category=1  ?min_price=10  ?max_price=100  ?in_stock=true
    Search:   ?search=keyboard
    Sorting:  ?ordering=price  or  ?ordering=-price
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at", "name", "stock"]

    def get_queryset(self):
        qs = Product.objects.select_related("category")
        user = self.request.user
        # Regular users only see active products; staff see everything.
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
        return qs

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Product appears in past orders. Set is_active=false instead of deleting."},
                status=status.HTTP_409_CONFLICT,
            )


# ---------- Orders ----------

class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Users see and create their own orders. Staff can see all orders."""
    serializer_class = OrderSerializer
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "total"]

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items__product")
        if getattr(self, "swagger_fake_view", False):  # used when generating API docs
            return qs.none()
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a pending order and put its items back in stock."""
        with transaction.atomic():
            order = self.get_object()
            if order.status != Order.Status.PENDING:
                return Response(
                    {"detail": f"Only pending orders can be cancelled (this one is {order.status})."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for item in order.items.all():
                Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status"])
        return Response(self.get_serializer(order).data)


# ---------- Admin stats ----------

class StatsView(APIView):
    """Quick shop overview (staff only)."""
    permission_classes = [IsAdminUser]

    @extend_schema(responses={200: dict})
    def get(self, request):
        valid = Order.objects.exclude(status=Order.Status.CANCELLED)
        low_stock = Product.objects.filter(is_active=True, stock__lte=5).order_by("stock")
        return Response({
            "orders": Order.objects.count(),
            "revenue": valid.aggregate(total=Sum("total"))["total"] or 0,
            "products": Product.objects.count(),
            "low_stock": [{"id": p.id, "name": p.name, "stock": p.stock} for p in low_stock],
        })
