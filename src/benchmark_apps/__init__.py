"""
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from src.benchmark_apps.base_benchmark_app import BenchmarkApp, CallbackType, RealApp
from src.benchmark_apps.calculator import Calculator
from src.benchmark_apps.click_count import ClickCount
from src.benchmark_apps.compiler import Compiler
from src.benchmark_apps.credit_card_service import CreditCardService
from src.benchmark_apps.forum import Forum
from src.benchmark_apps.login import Login
from src.benchmark_apps.monitor import Monitor
from src.benchmark_apps.product_catalog import ProductCatalog
from src.benchmark_apps.recipes import Recipes
from src.benchmark_apps.recommendation_service import RecommendationService
from src.benchmark_apps.secret_storage import SecretStorage
from src.benchmark_apps.shop_overview import ShopOverview
from src.benchmark_apps.shopping_cart_service import ShoppingCartService
from src.benchmark_apps.uptime_service import UptimeService
from src.benchmark_apps.user_creation import UserCreation
from src.benchmark_apps.wiki import Wiki

all_benchmark_apps = [
    Calculator,
    ClickCount,
    Compiler,
    CreditCardService,
    Forum,
    Login,
    Monitor,
    ProductCatalog,
    Recipes,
    RecommendationService,
    SecretStorage,
    ShopOverview,
    ShoppingCartService,
    UptimeService,
    UserCreation,
    Wiki,
]
