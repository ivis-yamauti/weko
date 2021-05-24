# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2018 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Query parser."""

from datetime import datetime

import six
from elasticsearch_dsl import Q
from flask import current_app
from invenio_pidstore.models import PersistentIdentifier
from invenio_records.models import RecordMetadata
from invenio_search import RecordsSearch, current_search_client
from weko_index_tree.models import Index
from werkzeug.utils import cached_property, import_string

from . import current_oaiserver


def query_string_parser(search_pattern):
    """Elasticsearch query string parser."""
    if not hasattr(current_oaiserver, 'query_parser'):
        query_parser = current_app.config['OAISERVER_QUERY_PARSER']
        if isinstance(query_parser, six.string_types):
            query_parser = import_string(query_parser)
        current_oaiserver.query_parser = query_parser
    return current_oaiserver.query_parser('query_string', query=search_pattern)


class OAIServerSearch(RecordsSearch):
    """Define default filter for quering OAI server."""

    class Meta:
        """Configuration for OAI server search."""

        default_filter = Q('exists', field='_oai.id')


def get_affected_records(spec=None, search_pattern=None):
    """Get list of affected records.

    :param spec: The record spec.
    :param search_pattern: The search pattern.
    :returns: An iterator to lazily find results.
    """
    # spec       pattern    query
    # ---------- ---------- -------
    # None       None       None
    # None       Y          Y
    # X          None       X
    # X          ''         X
    # X          Y          X OR Y

    if spec is None and search_pattern is None:
        raise StopIteration

    queries = []

    if spec is not None:
        queries.append(Q('match', **{'_oai.sets': spec}))

    if search_pattern:
        queries.append(query_string_parser(search_pattern=search_pattern))

    search = OAIServerSearch(
        index=current_app.config['OAISERVER_RECORD_INDEX'],
    ).query(Q('bool', should=queries))

    for result in search.scan():
        yield result.meta.id


def get_records(**kwargs):
    """Get records paginated."""
    def index_ids_has_future_date():
        """Get indexes."""
        query = Index.query.filter(
            Index.public_state.is_(True),
            Index.public_date > datetime.now(),
            Index.harvest_public_state.is_(True)
        )
        indexes = query.all() or []
        index_ids = [index.id for index in indexes]
        return index_ids

    def get_records_has_doi():
        """Get object_uuid of PersistentIdentifier."""
        # Get object_uuid of PersistentIdentifier
        query = PersistentIdentifier.query.filter(
            PersistentIdentifier.pid_type == 'doi'
        )
        pids = query.all() or []
        object_uuids = [pid.object_uuid for pid in pids]
        # Get RecordMetadata
        query = RecordMetadata.query.filter(
            RecordMetadata.id.in_(object_uuids)
        )
        records = query.all() or []
        return records

    def add_condition_doi_and_future_date(query):
        """Add condition which do not get DOI."""
        index_ids = index_ids_has_future_date()
        records = get_records_has_doi()
        for record in records:
            paths = record.json.get('path', [])
            for path in paths:
                if path in index_ids:
                    query = query.post_filter(
                        'bool',
                        **{'must_not': [
                            {'term': {'_id': str(record.id)}}]})
                    continue

    from weko_index_tree.api import Indexes
    page_ = kwargs.get('resumptionToken', {}).get('page', 1)
    size_ = current_app.config['OAISERVER_PAGE_SIZE']
    scroll = current_app.config['OAISERVER_RESUMPTION_TOKEN_EXPIRE_TIME']
    scroll_id = kwargs.get('resumptionToken', {}).get('scroll_id')

    if not scroll_id:
        search = OAIServerSearch(
            index=current_app.config['INDEXER_DEFAULT_INDEX'],
        ).params(
            scroll='{0}s'.format(scroll),
        ).extra(
            version='true',
        ).sort(
            {'control_number': {'order': 'asc'}}
        )[(page_ - 1) * size_:page_ * size_]

        if 'set' in kwargs:
            search = search.query('match', **{'_oai.sets': kwargs['set']})

        time_range = {}
        if 'from_' in kwargs:
            time_range['gte'] = kwargs['from_']
        if 'until' in kwargs:
            time_range['lte'] = kwargs['until']
        if time_range:
            search = search.filter('range', **{'_updated': time_range})

        search = search.query('match', **{'relation_version_is_last': 'true'})
        index_paths = Indexes.get_harverted_index_list()
        query_filter = [
            # script get deleted items.
            {"bool": {"must_not": {"exists": {"field": "path"}}}}
        ]
        for index_path in index_paths:
            query_filter.append({
                "wildcard": {
                    "path": index_path
                }
            })
        search = search.query(
            'bool', **{'must': [{'bool': {'should': query_filter}}]})
        add_condition_doi_and_future_date(search)
        response = search.execute().to_dict()
    else:
        response = current_search_client.scroll(
            scroll_id=scroll_id,
            scroll='{0}s'.format(scroll),
        )

    class Pagination(object):
        """Dummy pagination class."""

        page = page_
        per_page = size_

        def __init__(self, response):
            """Initilize pagination."""
            self.response = response
            self.total = response['hits']['total']
            self._scroll_id = response.get('_scroll_id')

            # clean descriptor on last page
            if not self.has_next:
                current_search_client.clear_scroll(
                    scroll_id=self._scroll_id
                )
                self._scroll_id = None

        @cached_property
        def has_next(self):
            """Return True if there is next page."""
            return self.page * self.per_page <= self.total

        @cached_property
        def next_num(self):
            """Return next page number."""
            return self.page + 1 if self.has_next else None

        @property
        def items(self):
            """Return iterator."""
            from datetime import datetime
            for result in self.response['hits']['hits']:
                if '_oai' in result['_source']:
                    yield {
                        'id': result['_id'],
                        'json': result,
                        'updated': datetime.strptime(
                            result['_source']['_updated'][:19],
                            '%Y-%m-%dT%H:%M:%S'
                        ),
                    }

    return Pagination(response)
