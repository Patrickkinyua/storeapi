from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Category, Product

User = get_user_model()


class ShopAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pw", is_staff=True)
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        cat = Category.objects.create(name="Gadgets")
        self.mouse = Product.objects.create(category=cat, name="Mouse", price="20.00", stock=5)
        self.hidden = Product.objects.create(category=cat, name="Old", price="5.00", stock=1, is_active=False)

    # --- catalogue ---
    def test_anyone_can_list_products_but_inactive_hidden(self):
        r = self.client.get("/api/products/")
        self.assertEqual(r.status_code, 200)
        names = [p["name"] for p in r.data["results"]]
        self.assertEqual(names, ["Mouse"])

    def test_filter_and_search(self):
        r = self.client.get("/api/products/?min_price=10&search=mou&in_stock=true")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get("/api/products/?min_price=50")
        self.assertEqual(r.data["count"], 0)

    def test_only_staff_can_create_products(self):
        payload = {"name": "Pad", "price": "3.00", "stock": 1, "category": self.mouse.category_id}
        self.assertEqual(self.client.post("/api/products/", payload).status_code, 401)  # not logged in
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.post("/api/products/", payload).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post("/api/products/", payload).status_code, 201)

    def test_negative_price_rejected(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/products/", {"name": "X", "price": "-1", "stock": 1,
                                                "category": self.mouse.category_id})
        self.assertEqual(r.status_code, 400)

    # --- auth ---
    def test_register_and_token_login(self):
        r = self.client.post("/api/auth/register/", {"username": "new", "password": "S0methingStrong!"})
        self.assertEqual(r.status_code, 201)
        self.assertIn("token", r.data)
        r = self.client.post("/api/auth/token/", {"username": "new", "password": "S0methingStrong!"})
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
        self.assertEqual(self.client.get("/api/auth/me/").data["username"], "new")

    # --- orders ---
    def test_orders_require_login(self):
        self.assertEqual(self.client.get("/api/orders/").status_code, 401)

    def test_place_order_reduces_stock_and_totals(self):
        self.client.force_authenticate(self.alice)
        r = self.client.post("/api/orders/", {"items": [{"product": self.mouse.pk, "quantity": 2}]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(str(r.data["total"]), "40.00")
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock, 3)

    def test_cannot_order_more_than_stock(self):
        self.client.force_authenticate(self.alice)
        r = self.client.post("/api/orders/", {"items": [{"product": self.mouse.pk, "quantity": 99}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock, 5)  # untouched, order rolled back

    def test_cannot_order_inactive_product(self):
        self.client.force_authenticate(self.alice)
        r = self.client.post("/api/orders/", {"items": [{"product": self.hidden.pk, "quantity": 1}]}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_users_only_see_own_orders(self):
        self.client.force_authenticate(self.alice)
        oid = self.client.post("/api/orders/", {"items": [{"product": self.mouse.pk, "quantity": 1}]},
                               format="json").data["id"]
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get("/api/orders/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/orders/{oid}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/orders/").data["count"], 1)

    def test_cancel_restores_stock_once(self):
        self.client.force_authenticate(self.alice)
        oid = self.client.post("/api/orders/", {"items": [{"product": self.mouse.pk, "quantity": 2}]},
                               format="json").data["id"]
        r = self.client.post(f"/api/orders/{oid}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "cancelled")
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock, 5)
        self.assertEqual(self.client.post(f"/api/orders/{oid}/cancel/").status_code, 400)

    def test_cannot_delete_product_with_orders(self):
        self.client.force_authenticate(self.alice)
        self.client.post("/api/orders/", {"items": [{"product": self.mouse.pk, "quantity": 1}]}, format="json")
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"/api/products/{self.mouse.pk}/").status_code, 409)

    # --- stats ---
    def test_stats_staff_only(self):
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.get("/api/stats/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/stats/").status_code, 200)
