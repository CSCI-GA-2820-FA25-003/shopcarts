"""
Test Factory to make fake objects for testing
"""

import factory
from factory.fuzzy import FuzzyChoice, FuzzyDecimal, FuzzyInteger
from service.models import Shopcart, ShopcartItem


class ShopcartFactory(factory.Factory):
    """Creates fake Shopcarts for testing"""

    class Meta:  # pylint: disable=too-few-public-methods
        """Maps factory to data model"""

        model = Shopcart

    id = factory.Sequence(lambda n: n)
    customer_id = factory.Sequence(lambda n: n + 1)
    created_date = factory.Faker("date_time")
    last_modified = factory.Faker("date_time")
    status = FuzzyChoice(choices=["active", "abandoned"])
    total_items = FuzzyInteger(0, 10)


class ShopcartItemFactory(factory.Factory):
    """Creates fake ShopcartItems for testing"""

    class Meta:  # pylint: disable=too-few-public-methods
        """Maps factory to data model"""

        model = ShopcartItem

    id = factory.Sequence(lambda n: n)
    shopcart_id = None  # Must be set manually or via relationship
    product_id = FuzzyInteger(1, 1000)
    description = factory.Faker("sentence", nb_words=5)
    quantity = FuzzyInteger(1, 10)
    price = FuzzyDecimal(0.99, 999.99, precision=2)
