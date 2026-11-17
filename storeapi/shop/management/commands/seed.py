from django.core.management.base import BaseCommand

from shop.models import Category, Product

DATA = {
    "Electronics": [
        ("Wireless Mouse", "Ergonomic 2.4GHz mouse", "19.99", 40),
        ("Mechanical Keyboard", "Blue switches, full size", "59.00", 15),
        ("USB-C Hub", "7-in-1 hub with HDMI", "34.50", 3),
        ("Webcam 1080p", "Plug and play", "42.00", 0),
    ],
    "Books": [
        ("Learning Python", "Beginner to intermediate", "29.95", 25),
        ("Clean Code", "A handbook of agile software craftsmanship", "38.00", 10),
    ],
    "Office": [
        ("Desk Lamp", "LED, adjustable", "24.00", 18),
        ("Notebook (3-pack)", "A5 ruled", "7.50", 100),
    ],
}


class Command(BaseCommand):
    help = "Load demo categories and products"

    def handle(self, *args, **options):
        for cat_name, products in DATA.items():
            cat, _ = Category.objects.get_or_create(name=cat_name)
            for name, desc, price, stock in products:
                Product.objects.get_or_create(
                    name=name,
                    defaults={"category": cat, "description": desc, "price": price, "stock": stock},
                )
        self.stdout.write(self.style.SUCCESS("Demo data loaded."))
