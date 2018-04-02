from collections import OrderedDict
from decimal import ROUND_DOWN
from functools import wraps
from time import time

import requests

from ufobit.utils import Decimal

DEFAULT_CACHE_TIME = 60

# Constant for use in deriving exchange
# rates when given in terms of 1 BTC.
ONE = Decimal(1)

# https://en.bitcoin.it/wiki/Units
SATOSHI = 1
uBTC = 10 ** 2
mBTC = 10 ** 5
BTC = 10 ** 8

SUPPORTED_CURRENCIES = OrderedDict([
    ('satoshi', 'Satoshi'),
    ('ubtc', 'Microbitcoin'),
    ('mbtc', 'Millibitcoin'),
    ('btc', 'Bitcoin'),
    ('usd', 'United States Dollar'),
    ('eur', 'Eurozone Euro'),
    ('gbp', 'Pound Sterling'),
    ('jpy', 'Japanese Yen'),
    ('cny', 'Chinese Yuan'),
    ('cad', 'Canadian Dollar'),
    ('aud', 'Australian Dollar'),
    ('nzd', 'New Zealand Dollar'),
    ('rub', 'Russian Ruble'),
    ('brl', 'Brazilian Real'),
    ('chf', 'Swiss Franc'),
    ('sek', 'Swedish Krona'),
    ('dkk', 'Danish Krone'),
    ('isk', 'Icelandic Krona'),
    ('pln', 'Polish Zloty'),
    ('hkd', 'Hong Kong Dollar'),
    ('krw', 'South Korean Won'),
    ('sgd', 'Singapore Dollar'),
    ('thb', 'Thai Baht'),
    ('twd', 'New Taiwan Dollar'),
    ('clp', 'Chilean Peso')
])

# https://en.wikipedia.org/wiki/ISO_4217
CURRENCY_PRECISION = {
    'satoshi': 0,
    'ubtc': 2,
    'mbtc': 5,
    'btc': 8,
    'usd': 2,
    'eur': 2,
    'gbp': 2,
    'jpy': 0,
    'cny': 2,
    'cad': 2,
    'aud': 2,
    'nzd': 2,
    'rub': 2,
    'brl': 2,
    'chf': 2,
    'sek': 2,
    'dkk': 2,
    'isk': 2,
    'pln': 2,
    'hkd': 2,
    'krw': 0,
    'sgd': 2,
    'thb': 2,
    'twd': 2,
    'clp': 0
}


def set_rate_cache_time(seconds):
    global DEFAULT_CACHE_TIME
    DEFAULT_CACHE_TIME = seconds


def satoshi_to_satoshi():
    return SATOSHI


def ubtc_to_satoshi():
    return uBTC


def mbtc_to_satoshi():
    return mBTC


def btc_to_satoshi():
    return BTC


class UFORates:
    MAIN_ENDPOINT = 'https://api.coinmarketcap.com/v1/ticker/uniform-fiscal-object/'

    @classmethod
    def currency_to_ufoshi(cls, currency):
        r = requests.get(cls.MAIN_ENDPOINT, params={'convert': currency})
        rate = r.json()[0]['price_' + currency.lower()]
        return int(ONE / Decimal(rate) * BTC)

    @classmethod
    def usd_to_ufoshi(cls):
        return cls.currency_to_ufoshi('usd')

    @classmethod
    def rub_to_ufoshi(cls):
        return cls.currency_to_ufoshi('rub')


class RatesAPI:
    """Each method converts exactly 1 unit of the currency to the equivalent
    number of satoshi.
    """
    IGNORED_ERRORS = (requests.exceptions.ConnectionError,
                      requests.exceptions.Timeout)

    USD_RATES = [UFORates.usd_to_ufoshi]
    RUB_RATES = [UFORates.rub_to_ufoshi]

    @classmethod
    def usd_to_satoshi(cls):  # pragma: no cover

        for api_call in cls.USD_RATES:
            try:
                return api_call()
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def rub_to_satoshi(cls):  # pragma: no cover

        for api_call in cls.RUB_RATES:
            try:
                return api_call()
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

EXCHANGE_RATES = {
    'satoshi': satoshi_to_satoshi,
    'ubtc': ubtc_to_satoshi,
    'mbtc': mbtc_to_satoshi,
    'btc': btc_to_satoshi,
    'usd': RatesAPI.usd_to_satoshi,
    'rub': RatesAPI.rub_to_satoshi,
}


def currency_to_satoshi(amount, currency):
    """Converts a given amount of currency to the equivalent number of
    satoshi. The amount can be either an int, float, or string as long as
    it is a valid input to :py:class:`decimal.Decimal`.

    :param amount: The quantity of currency.
    :param currency: One of the :ref:`supported currencies`.
    :type currency: ``str``
    :rtype: ``int``
    """
    satoshis = EXCHANGE_RATES[currency]()
    return int(satoshis * Decimal(amount))


class CachedRate:
    __slots__ = ('satoshis', 'last_update')

    def __init__(self, satoshis, last_update):
        self.satoshis = satoshis
        self.last_update = last_update


def currency_to_satoshi_local_cache(f):
    start_time = time()

    cached_rates = dict([
        (currency, CachedRate(None, start_time)) for currency in EXCHANGE_RATES.keys()
    ])

    @wraps(f)
    def wrapper(amount, currency):
        now = time()

        cached_rate = cached_rates[currency]

        if not cached_rate.satoshis or now - cached_rate.last_update > DEFAULT_CACHE_TIME:
            cached_rate.satoshis = EXCHANGE_RATES[currency]()
            cached_rate.last_update = now

        return int(cached_rate.satoshis * Decimal(amount))

    return wrapper


@currency_to_satoshi_local_cache
def currency_to_satoshi_local_cached():
    pass  # pragma: no cover


def currency_to_satoshi_cached(amount, currency):
    """Converts a given amount of currency to the equivalent number of
    satoshi. The amount can be either an int, float, or string as long as
    it is a valid input to :py:class:`decimal.Decimal`. Results are cached
    using a decorator for 60 seconds by default. See :ref:`cache times`.

    :param amount: The quantity of currency.
    :param currency: One of the :ref:`supported currencies`.
    :type currency: ``str``
    :rtype: ``int``
    """
    return currency_to_satoshi_local_cached(amount, currency)


def satoshi_to_currency(num, currency):
    """Converts a given number of satoshi to another currency as a formatted
    string rounded down to the proper number of decimal places.

    :param num: The number of satoshi.
    :type num: ``int``
    :param currency: One of the :ref:`supported currencies`.
    :type currency: ``str``
    :rtype: ``str``
    """
    return '{:f}'.format(
        Decimal(
            num / Decimal(EXCHANGE_RATES[currency]())
        ).quantize(
            Decimal('0.' + '0' * CURRENCY_PRECISION[currency]),
            rounding=ROUND_DOWN
        ).normalize()
    )


def satoshi_to_currency_cached(num, currency):
    """Converts a given number of satoshi to another currency as a formatted
    string rounded down to the proper number of decimal places. Results are
    cached using a decorator for 60 seconds by default. See :ref:`cache times`.

    :param num: The number of satoshi.
    :type num: ``int``
    :param currency: One of the :ref:`supported currencies`.
    :type currency: ``str``
    :rtype: ``str``
    """
    return '{:f}'.format(
        Decimal(
            num / Decimal(currency_to_satoshi_cached(1, currency))
        ).quantize(
            Decimal('0.' + '0' * CURRENCY_PRECISION[currency]),
            rounding=ROUND_DOWN
        ).normalize()
    )
