from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("products", views.ProductViewSet, basename="product")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view()),
    path("auth/token/", obtain_auth_token),
    path("auth/me/", views.MeView.as_view()),
    path("stats/", views.StatsView.as_view()),
] + router.urls
