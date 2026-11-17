# Ricky Stores API

Django REST Framework API: categories, products, orders, token auth.
Interactive docs live at `/api/docs/` once it's running.

## Endpoints

| Method | Path | Who | What |
|---|---|---|---|
| POST | `/api/auth/register/` | anyone | Create account, returns token |
| POST | `/api/auth/token/` | anyone | Log in (username + password), returns token |
| GET | `/api/auth/me/` | logged in | Who am I |
| GET | `/api/categories/` | anyone | List categories (with product counts) |
| POST/PUT/PATCH/DELETE | `/api/categories/{id}/` | staff | Manage categories |
| GET | `/api/products/` | anyone | List products. Supports `?search=` `?category=` `?min_price=` `?max_price=` `?in_stock=true` `?ordering=-price` `?page=2` |
| GET | `/api/products/{id}/` | anyone | One product |
| POST/PUT/PATCH/DELETE | `/api/products/` ... | staff | Manage products |
| POST | `/api/orders/` | logged in | Place an order (checks + reduces stock) |
| GET | `/api/orders/`, `/api/orders/{id}/` | logged in | Your orders (staff see all) |
| POST | `/api/orders/{id}/cancel/` | logged in | Cancel pending order, restock items |
| GET | `/api/stats/` | staff | Revenue, order count, low-stock list |

Send the token as a header: `Authorization: Token <your-token>`

## Run locally

    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env          # then edit it
    python manage.py migrate
    python manage.py seed         # demo data
    python manage.py createsuperuser
    python manage.py runserver

## Deploy to the Azure VM

See the steps in the chat; the service and nginx files are in `deploy/`.

## Deploying from GitHub

    # one-time on the VM
    git clone https://github.com/<you>/storeapi.git && cd storeapi
    # ...venv, .env, migrate, seed, service + nginx as above...

    # every update after that
    ./deploy/update.sh

`.github/workflows/deploy.yml` can run this automatically on every push to `main`
(needs repo secrets VM_HOST, VM_USER, VM_SSH_KEY, and passwordless `sudo systemctl restart api` on the VM).
