# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 National Institute of Informatics.
#
# weko-gridlayout is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Module of weko-gridlayout."""

WEKO_GRIDLAYOUT_BASE_TEMPLATE = 'weko_gridlayout/base.html'
"""Default base template for the demo page."""

WEKO_GRIDLAYOUT_ADMIN_CREATE_WIDGET_SETTINGS = \
    'weko_gridlayout/admin/create_widget_settings.html'

WEKO_GRIDLAYOUT_ADMIN_EDIT_WIDGET_SETTINGS = \
    'weko_gridlayout/admin/edit_widget_settings.html'
"""Widget templates."""

WEKO_GRIDLAYOUT_ADMIN_WIDGET_DESIGN = \
    'weko_gridlayout/admin/widget_design.html'
"""Widget Design templates."""

WEKO_GRIDLAYOUT_DEFAULT_PAGES_TEMPLATE = \
    'weko_gridlayout/pages/default_page.html'
"""Widget Design templates."""

WEKO_GRIDLAYOUT_DEFAULT_WIDGET_LABEL = "No Title"
"""Default widget label"""

WEKO_GRIDLAYOUT_DEFAULT_LANGUAGE_CODE = "en"
"""Default widget language code"""

WEKO_GRIDLAYOUT_DEFAULT_DISPLAY_RESULT = "5"
"""Default new arrivals display result"""

WEKO_GRIDLAYOUT_DEFAULT_NEW_DATE = "5"
"""Default new arrivals new date"""

WEKO_GRIDLAYOUT_ACCESS_COUNTER_TYPE = "Access counter"
"""Access counter type"""

WEKO_GRIDLAYOUT_NEW_ARRIVALS_TYPE = "New arrivals"
"""New arrivals type"""

WEKO_GRIDLAYOUT_NOTICE_TYPE = "Notice"
"""Notice type"""

WEKO_GRIDLAYOUT_MAIN_TYPE = "Main contents"
"""Main contents widget type."""

WEKO_XML_FORMAT = \
    '<?xml version="1.0" encoding="UTF-8"?>'
"""Default setting for xml"""

WEKO_XMLNS = \
    'http://purl.org/rss/1.0/'
"""Default XMLNS url"""

WEKO_XMLNS_RDF = \
    'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
"""Default XMLNS RDF url"""

WEKO_XMLNS_RDFS = \
    'http://www.w3.org/2000/01/rdf-schema#'
"""Default XMLNS RDFS url"""

WEKO_XMLNS_DC = \
    'http://purl.org/dc/elements/1.1/'
"""Default XMLNS DC url"""

WEKO_XMLNS_PRISM = \
    'http://prismstandard.org/namespaces/basic/2.0/'
"""Default XMLNS PRISM url"""

WEKO_RDF_SCHEMA = \
    'https://www.w3.org/TR/rdf-schema/'
"""Defaul RDF Schema"""

WEKO_GRIDLAYOUT_MENU_WIDGET_TYPE = 'Menu'
"""Menu widget type name."""

WEKO_GRIDLAYOUT_HEADER_WIDGET_TYPE = 'Header'
"""Header widget type name."""

WEKO_GRIDLAYOUT_WIDGET_DEFAULT_COLOR = '#4169E1'
"""Default HTML color for widget components."""

WEKO_GRIDLAYOUT_AUTO_ADJUST_THE_HEIGHT = True
"""Auto adjust the height of the widget on Top page"""

WEKO_GRIDLAYOUT_COMPRESS_LEVEL = 6
"""Compress level"""

WEKO_GRIDLAYOUT_IS_COMPRESS_WIDGET = True
"""Enable compress widget setting response"""

WEKO_GRIDLAYOUT_WIDGET_CACHE_KEY = "widget_cache"
"""The Widget cache key"""

WEKO_GRIDLAYOUT_WIDGET_PAGE_CACHE_KEY = "widget_page_cache"
"""The Page cache key"""

WEKO_GRIDLAYOUT_BUCKET_UUID = "517f7d98-ab2c-4736-91ea-54ba34e7905d"
"""The Gridlayout bucket UUID"""

WEKO_GRIDLAYOUT_FILE_MAX_SIZE = 1024 * 1024 * 16  # 16 MB
"""Allowed file size for the widget static files."""

WEKO_GRIDLAYOUT_WIDGET_ITEM_LOCK_KEY = "locked_widget_key_{}"
"""Widget item lock key."""
