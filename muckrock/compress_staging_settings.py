"""
Settings for compressing staging assets
"""

# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import

from settings import *

BUCKET_NAME = 'muckrock-staging'
STATIC_URL = 'https://' + BUCKET_NAME + '.s3.amazonaws.com/'
COMPRESS_ENABLED = True