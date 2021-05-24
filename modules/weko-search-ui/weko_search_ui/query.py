# -*- coding: utf-8 -*-
#
# This file is part of WEKO3.
# Copyright (C) 2017 National Institute of Informatics.
#
# WEKO3 is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# WEKO3 is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WEKO3; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.

"""Query factories for REST API."""

import json
import sys
from datetime import datetime
from functools import partial

from elasticsearch_dsl.query import Q
from flask import current_app, request
from flask.helpers import flash
from flask_babelex import gettext as _
from flask_security import current_user
from invenio_communities.models import Community
from invenio_records_rest.errors import InvalidQueryRESTError
from weko_index_tree.api import Indexes
from werkzeug.datastructures import MultiDict

from . import config
from .api import SearchSetting
from .permissions import search_permission


def get_item_type_aggs(search_index):
    """Get item types aggregations.

    :return: aggs dict
    """
    facets = None
    if search_permission.can():
        facets = current_app.config['RECORDS_REST_FACETS']
    else:
        facets = current_app.config['RECORDS_REST_FACETS_NO_SEARCH_PERMISSION']

    return facets.get(search_index).get("aggs", {})


def get_permission_filter(comm_id=None):
    """Get permission filter."""
    # check permission
    is_perm = search_permission.can()
    match = Q('match', publish_status='0')
    version = Q('match', relation_version_is_last='true')
    rng = Q('range', **{'publish_date': {'lte': 'now/d'}})
    term_list = []
    mst = []
    is_perm_paths = Indexes.get_browsing_tree_paths()
    search_type = request.values.get('search_type')

    if comm_id:

        if search_type == config.WEKO_SEARCH_TYPE_DICT['FULL_TEXT']:
            self_path = Indexes.get_self_path(comm_id)

            if self_path and self_path.path in is_perm_paths:
                term_list.append(self_path.path)

            path = term_list[0] + '*'
            should_path = []
            wildcard_path = Q("wildcard", path=path)
            should_path.append(wildcard_path)

            mst.append(match)
            mst.append(rng)
            terms = Q('bool', should=should_path)
        else:   # In case search_type is keyword or index
            self_path = Indexes.get_self_path(comm_id)

            if self_path and self_path.path in is_perm_paths:
                term_list.append(self_path.path)

            mst.append(match)
            mst.append(rng)
            terms = Q('terms', path=term_list)
    else:
        mst.append(match)
        mst.append(rng)
        terms = Q('terms', path=is_perm_paths)

    mut = []

    if is_perm:
        user_id, result = check_admin_user()

        if result:
            shuld = [Q('match', weko_creator_id=user_id),
                     Q('match', weko_shared_id=user_id)]
            shuld.append(Q('bool', must=mst))
            mut.append(Q('bool', should=shuld, must=[terms]))
            mut.append(Q('bool', must=version))
    else:
        mut = mst
        mut.append(terms)
        base_mut = [match, version]
        mut.append(Q('bool', must=base_mut))

    return mut


def default_search_factory(self, search, query_parser=None, search_type=None):
    """Parse query using Weko-Query-Parser. MetaData Search.

    :param self: REST view.
    :param search: Elastic search DSL search instance.
    :param query_parser: Query parser. (Default: ``None``)
    :param search_type: Search type. (Default: ``None``)
    :returns: Tuple with search instance and URL arguments.
    """
    def _get_search_qs_query(qs=None):
        """Qs of search bar keywords for detail simple search.

        :param qs: Query string.
        :return: Query parser.
        """
        q = Q(
            'query_string',
            query=qs,
            default_operator='and',
            fields=['search_*', 'search_*.ja']
        ) if qs else None

        return q

    def _get_detail_keywords_query():
        """Get keywords query.

        :return: Query parser.
        """
        def _get_keywords_query(k, v):
            qry = None
            kv = request.values.get(
                'lang'
            ) if k == 'language' else request.values.get(k)

            if not kv:
                return

            if isinstance(v, str):
                name_dict = dict(operator="and")
                name_dict.update(dict(query=kv))
                qry = Q('match', **{v: name_dict})
            elif isinstance(v, list):
                qry = Q('multi_match', query=kv, type='most_fields',
                        minimum_should_match='75%',
                        operator='and', fields=v)
            elif isinstance(v, dict):

                for key, vlst in v.items():

                    if isinstance(vlst, list):
                        shud = []
                        kvl = [
                            x for x in kv.split(',')
                            if x.isdecimal() and int(x) < len(vlst) + 1
                        ]

                        for j in map(
                                partial(lambda x, y: x[int(y)], vlst), kvl):
                            name_dict = dict(operator="and")
                            name_dict.update(dict(query=j))
                            shud.append(Q('match', **{key: name_dict}))

                        kvl = [x for x in kv.split(',')
                               if not x.isdecimal() and x in vlst]

                        for j in kvl:
                            name_dict = dict(operator="and")
                            name_dict.update(dict(query=j))
                            shud.append(Q('match', **{key: name_dict}))

                        if shud:
                            return Q('bool', should=shud)

            elif isinstance(v, tuple) and len(v) >= 2:
                shud = []

                for i in map(lambda x: v[1](x), kv.split(',')):
                    shud.append(Q('match', **{v[0]: i}))

                if shud:
                    qry = Q('bool', should=shud)

            return qry

        def _get_nested_query(k, v):
            # text value
            kv = request.values.get(k)

            if not kv:
                return

            shuld = []

            if isinstance(v, tuple) and len(v) > 1 and isinstance(v[1], dict):
                # attr keyword in request url
                for attr_key, attr_val_str in map(
                    lambda x: (
                        x, request.values.get(x)), list(
                        v[1].keys())):
                    attr_obj = v[1].get(attr_key)

                    if isinstance(attr_obj, dict) and attr_val_str:

                        if isinstance(v[0], str) and not len(v[0]):

                            # For ID search
                            for key in attr_val_str.split(','):
                                attr = attr_obj.get(key)

                                if isinstance(attr, tuple):
                                    attr = [attr]

                                if isinstance(attr, list):
                                    for alst in attr:
                                        if isinstance(alst, tuple):
                                            val_attr_lst = alst[1].split('=')
                                            name = alst[0] + ".value"
                                            name_dict = dict(operator="and")
                                            name_dict.update(dict(query=kv))
                                            mut = [
                                                Q('match',
                                                  **{name: name_dict})]
                                            qt = None

                                            if '=*' in alst[1]:
                                                name = alst[0] + \
                                                    "." + val_attr_lst[0]
                                                qt = [
                                                    Q('term',
                                                      **{name:
                                                         val_attr_lst[1]})]

                                            mut.extend(qt or [])
                                            qry = Q('bool', must=mut)
                                            shuld.append(
                                                Q('nested', path=alst[0],
                                                  query=qry))
                        else:
                            attr_key_hit = [
                                x for x in attr_obj.keys() if v[0] + "." in x]

                            if attr_key_hit:
                                vlst = attr_obj.get(attr_key_hit[0])

                                if isinstance(vlst, list):
                                    attr_val = [x for x in attr_val_str.split(
                                        ',') if x.isdecimal()
                                        and int(x) < len(vlst)]

                                    if attr_val:
                                        mst = []
                                        name = v[0] + ".value"
                                        qry = Q('multi_match', query=kv,
                                                type='most_fields',
                                                minimum_should_match='75%',
                                                operator='and', fields=[name])
                                        mst.append(qry)
                                        name = attr_key_hit[0]
                                        qm = Q('terms',
                                               **{name: list(map(partial(lambda m, n: m[int(n)], vlst), attr_val))})
                                        mst.append(qm)
                                        shuld.append(Q('nested', path=v[0],
                                                       query=Q(
                                                           'bool', must=mst)))

            return Q('bool', should=shuld) if shuld else None

        def _get_date_query(k, v):
            # text value
            qry = None

            if isinstance(v, list) and len(v) >= 2:
                date_from = request.values.get(k + "_" + v[0][0])
                date_to = request.values.get(k + "_" + v[0][1])

                if not date_from or not date_to:
                    return

                date_from = datetime.strptime(
                    date_from, '%Y%m%d').strftime('%Y-%m-%d')
                date_to = datetime.strptime(
                    date_to, '%Y%m%d').strftime('%Y-%m-%d')

                qv = {}
                qv.update(dict(gte=date_from))
                qv.update(dict(lte=date_to))

                if isinstance(v[1], str):
                    qry = Q('range', **{v[1]: qv})
                elif isinstance(v[1], tuple) and len(v[1]) >= 2:
                    path = v[1][0]
                    dt = v[1][1]

                    if isinstance(dt, dict):

                        for attr_key, attr_val_str in map(
                            lambda x: (
                                x, request.values.get(x)), list(
                                dt.keys())):
                            attr_obj = dt.get(attr_key)

                            if isinstance(attr_obj, dict) and attr_val_str:
                                attr_key_hit = [
                                    x for x in attr_obj.keys()
                                    if path + "." in x]

                                if attr_key_hit:
                                    vlst = attr_obj.get(attr_key_hit[0])

                                    if isinstance(vlst, list):
                                        attr_val = [
                                            x for x in attr_val_str.split(',')]
                                        shud = []
                                        for j in attr_val:
                                            qt = Q(
                                                'term', **{attr_key_hit[0]: j})
                                            shud.append(qt)

                                        qry = Q(
                                            'range', **{path + ".value": qv})
                                        qry = Q(
                                            'nested', path=path, query=Q(
                                                'bool', should=shud,
                                                must=[qry]))
            return qry

        kwd = current_app.config['WEKO_SEARCH_KEYWORDS_DICT']
        ks = kwd.get('string')
        kd = kwd.get('date')
        kn = kwd.get('nested')

        mut = []

        try:
            for k, v in ks.items():
                qy = _get_keywords_query(k, v)

                if qy:
                    mut.append(qy)

            for k, v in kn.items():
                qy = _get_nested_query(k, v)

                if qy:
                    mut.append(qy)

            for k, v in kd.items():
                qy = _get_date_query(k, v)

                if qy:
                    mut.append(qy)
        except Exception as e:
            current_app.logger.exception(
                'Detail search query parser failed. err:{0}'.format(e))

        return mut

    def _get_simple_search_query(qs=None):
        """Query parser for simple search.

        :param qs: Query string.
        :return: Query parser.
        """
        # add Permission filter by publish date and status
        mst = get_permission_filter()

        q = _get_search_qs_query(qs)

        if q:
            mst.append(q)

        mst.extend(_get_detail_keywords_query())

        return Q('bool', must=mst) if mst else Q()

    def _get_simple_search_community_query(community_id, qs=None):
        """Query parser for simple search.

        :param qs: Query string.
        :return: Query parser.
        """
        # add  Permission filter by publish date and status
        comm = Community.get(community_id)
        root_node_id = comm.root_node_id

        mst = get_permission_filter(root_node_id)
        q = _get_search_qs_query(qs)

        if q:
            mst.append(q)

        mst.extend(_get_detail_keywords_query())
        return Q('bool', must=mst) if mst else Q()

    def _get_file_content_query(qstr):
        """Query for searching indexed file contents."""
        multi_cont_q = Q('multi_match', query=qstr, operator='and',
                         fields=['content.attachment.content'])

        # Search fields may increase so leaving as multi
        multi_q = Q(
            'query_string',
            query=qs,
            default_operator='and',
            fields=['search_*', 'search_*.ja']
        )

        nested_content = Q('nested', query=multi_cont_q, path='content')
        return Q('bool', should=[nested_content, multi_q])

    def _default_parser(qstr=None):
        """Default parser that uses the Q() from elasticsearch_dsl.

           Full text Search.
           Detail Search.

        :param qstr: Query string.
        :returns: Query parser.
        """
        # add  Permission filter by publish date and status
        mst = get_permission_filter()

        # multi keywords search filter
        mkq = _get_detail_keywords_query()

        # detail search
        if mkq:
            mst.extend(mkq)
            q = _get_search_qs_query(qs)

            if q:
                mst.append(q)
        else:
            # Full Text Search
            if qstr:
                q_s = _get_file_content_query(qstr)
                mst.append(q_s)

        return Q('bool', must=mst) if mst else Q()

    def _default_parser_community(community_id, qstr=None):
        """Default parser that uses the Q() from elasticsearch_dsl.

           Full text Search.
           Detail Search.

        :param qstr: Query string.
        :returns: Query parser.
        """
        # add  Permission filter by publish date and status
        comm = Community.get(community_id)
        root_node_id = comm.root_node_id
        mst = get_permission_filter(root_node_id)

        # multi keywords search filter
        mkq = _get_detail_keywords_query()

        # detail search
        if mkq:
            mst.extend(mkq)
            q = _get_search_qs_query(qs)

            if q:
                mst.append(q)
        else:
            # Full Text Search
            if qstr:
                q_s = _get_file_content_query(qstr)
                mst.append(q_s)

        return Q('bool', must=mst) if mst else Q()

    from invenio_records_rest.facets import default_facets_factory
    from invenio_records_rest.sorter import default_sorter_factory

    # add by ryuu at 1004 start curate
    comm_ide = request.values.get('provisional_communities')

    # simple search
    comm_id_simple = request.values.get('community')

    # add by ryuu at 1004 end
    if comm_id_simple:
        query_parser = query_parser or _default_parser_community
    else:
        query_parser = query_parser or _default_parser

    if search_type is None:
        search_type = request.values.get('search_type')

    if request.values.get('format'):
        qs = request.values.get('keyword')
    else:
        # Escape special characters for avoiding ES search errors
        qs = (
            request.values.get('q', '')
            .replace('\\', r'\\')
            .replace('+', r'\+')
            .replace('-', r'\-')
            .replace('=', r'\=')
            .replace('&&', r'\&&')
            .replace('||', r'\||')
            .replace('!', r'\!')
            .replace('(', r'\(')
            .replace(')', r'\)')
            .replace('{', r'\{')
            .replace('}', r'\}')
            .replace('[', r'\[')
            .replace(']', r'\]')
            .replace('^', r'\^')
            .replace('"', r'\"')
            .replace('~', r'\~')
            .replace('*', r'\*')
            .replace('?', r'\?')
            .replace(':', r'\:')
            .replace('/', r'\/')
        )

        if '<' in qs or '>' in qs:
            flash(
                _('"<" and ">" cannot be used for searching.'),
                category='warning'
            )

    # full text search
    if search_type == config.WEKO_SEARCH_TYPE_DICT['FULL_TEXT']:
        if comm_id_simple:
            query_q = query_parser(comm_id_simple, qs)
        else:
            query_q = query_parser(qs)
    else:
        # simple search
        if comm_ide:
            query_q = _get_simple_search_community_query(comm_ide, qs)
        elif comm_id_simple:
            query_q = _get_simple_search_community_query(comm_id_simple, qs)
        else:
            query_q = _get_simple_search_query(qs)

    src = {'_source': {'excludes': ['content']}}
    search._extra.update(src)

    try:
        search = search.filter(query_q)
    except SyntaxError:
        current_app.logger.debug(
            "Failed parsing query: {0}".format(
                request.values.get('q', '')
            ),
            exc_info=True)
        raise InvalidQueryRESTError()

    search_index = search._index[0]
    search, urlkwargs = default_facets_factory(search, search_index)
    search, sortkwargs = default_sorter_factory(search, search_index)

    for key, value in sortkwargs.items():
        urlkwargs.add(key, value)

        # defalult sort
        if not sortkwargs:
            sort_key, sort = SearchSetting.get_default_sort(
                current_app.config['WEKO_SEARCH_TYPE_KEYWORD'])
            key_fileds = SearchSetting.get_sort_key(sort_key)
            if key_fileds:
                sort_obj = dict()
                nested_sorting = SearchSetting.get_nested_sorting(sort_key)

                if sort == 'desc':
                    sort_obj[key_fileds] = dict(order='desc',
                                                unmapped_type='long')
                    sort_key = '-' + sort_key
                else:
                    sort_obj[key_fileds] = dict(order='asc',
                                                unmapped_type='long')

                if nested_sorting:
                    sort_obj[key_fileds].update({'nested': nested_sorting})

                search._sort.append(sort_obj)

            urlkwargs.add('sort', sort_key)

    urlkwargs.add('q', query_q)
    return search, urlkwargs


def item_path_search_factory(self, search, index_id=None):
    """Parse query using Weko-Query-Parser.

    :param self: REST view.
    :param search: Elastic search DSL search instance.
    :param index_id: Index Identifier contains item's path
    :returns: Tuple with search instance and URL arguments.
    """
    def _get_index_earch_query():

        query_q = {
            "_source": {
                "excludes": ['content']
            },
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "path.tree": "@index"
                            }
                        },
                        {
                            "match": {
                                "relation_version_is_last": "true"
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "path": {
                    "terms": {
                        "field": "path",
                        "include": "@idxchild",
                        "size": "@count"
                    },
                    "aggs": {
                        "date_range": {
                            "filter": {
                                "match": {"publish_status": "0"}
                            },
                            "aggs": {
                                "available": {
                                    "range": {
                                        "field": "publish_date",
                                        "ranges": [
                                            {
                                                "from": "now+1d/d"
                                            },
                                            {
                                                "to": "now+1d/d"
                                            }
                                        ]
                                    },
                                }
                            }
                        },
                        "no_available": {
                            "filter": {
                                "bool": {
                                    "must_not": [
                                        {
                                            "match": {
                                                "publish_status": "0"
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            },
            "post_filter": {}
        }

        q = request.values.get('q') or '0' if index_id is None else index_id

        if q != '0':
            # add item type aggs
            query_q['aggs']['path']['aggs']. \
                update(get_item_type_aggs(search._index[0]))

            if q:
                mut = get_permission_filter(q)
            else:
                mut = get_permission_filter()

            if mut:
                mut = list(map(lambda x: x.to_dict(), mut))
                post_filter = query_q['post_filter']

                if mut[0].get('bool'):
                    post_filter['bool'] = mut[0]['bool']
                else:
                    post_filter['bool'] = {'must': mut}

            # create search query
            if q:
                try:
                    child_idx = Indexes.get_child_list_by_pip(q)
                    child_idx_str = ""
                    fp = Indexes.get_self_path(q)

                    for i in range(len(child_idx)):

                        if i != 0:
                            child_idx_str += "|" + str(child_idx[i][2])
                        else:
                            child_idx_str += str(child_idx[i][2])

                    query_q = json.dumps(query_q).replace("@index", fp.path)
                    query_q = json.loads(query_q)
                    query_q = json.dumps(query_q).replace(
                        "@idxchild", child_idx_str
                    )
                    query_q = json.loads(query_q)
                except BaseException as ex:
                    import traceback
                    traceback.print_exc(file=sys.stdout)

            count = str(Indexes.get_index_count())
            query_q = json.dumps(query_q).replace("@count", count)
            query_q = json.loads(query_q)

            return query_q
        else:
            # add item type aggs
            wild_card = []
            child_list = Indexes.get_child_list(q)

            if child_list:

                for item in child_list:
                    wc = {
                        "wildcard": {
                            "path.tree": item.cid
                        }
                    }
                    wild_card.append(wc)

            query_not_q = {
                "_source": {
                    "excludes": ["content"]
                },
                "query": {
                    "bool": {
                        "must": [
                            {
                                "bool": {
                                    "should": wild_card
                                }
                            },
                            {
                                "match": {
                                    "relation_version_is_last": "true"
                                }
                            }
                        ]
                    }
                },
                "aggs": {
                    "path": {
                        "terms": {
                            "field": "path",
                            "size": "@count"
                        },
                        "aggs": {
                            "date_range": {
                                "filter": {
                                    "match": {"publish_status": "0"}
                                },
                                "aggs": {
                                    "available": {
                                        "range": {
                                            "field": "publish_date",
                                            "ranges": [
                                                {
                                                    "from": "now+1d/d"
                                                },
                                                {
                                                    "to": "now+1d/d"
                                                }
                                            ]
                                        },
                                    }
                                }
                            },
                            "no_available": {
                                "filter": {
                                    "bool": {
                                        "must_not": [
                                            {
                                                "match": {
                                                    "publish_status": "0"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "post_filter": {}
            }

            query_not_q['aggs']['path']['aggs']. \
                update(get_item_type_aggs(search._index[0]))

            if q:
                mut = get_permission_filter(q)
            else:
                mut = get_permission_filter()

            if mut:
                mut = list(map(lambda x: x.to_dict(), mut))
                post_filter = query_not_q['post_filter']

                if mut[0].get('bool'):
                    post_filter['bool'] = mut[0]['bool']
                else:
                    post_filter['bool'] = {'must': mut}

            # create search query
            count = str(Indexes.get_index_count())
            query_not_q = json.dumps(query_not_q).replace("@count", count)
            query_not_q = json.loads(query_not_q)

            return query_not_q

    # create a index search query
    query_q = _get_index_earch_query()
    urlkwargs = MultiDict()

    try:
        # Aggregations.
        extr = search._extra.copy()
        search.update_from_dict(query_q)
        search._extra.update(extr)
    except SyntaxError:
        q = request.values.get('q', '') if index_id is None else index_id
        current_app.logger.debug(
            "Failed parsing query: {0}".format(q),
            exc_info=True)
        raise InvalidQueryRESTError()

    from invenio_records_rest.sorter import default_sorter_factory
    search_index = search._index[0]
    search, sortkwargs = default_sorter_factory(search, search_index)

    for key, value in sortkwargs.items():

        # set custom sort option
        if 'custom_sort' in value:
            ind_id = request.values.get('q', '')
            search._sort = []

            if value == 'custom_sort':
                script_str, default_sort = SearchSetting.get_custom_sort(
                    ind_id, 'asc')
            else:
                script_str, default_sort = SearchSetting.get_custom_sort(
                    ind_id, 'desc')

            search._sort.append(script_str)
            search._sort.append(default_sort)

        # set selectbox
        urlkwargs.add(key, value)

    # default sort
    if not sortkwargs:
        ind_id = request.values.get('q', '')
        root_flag = True if ind_id and ind_id == '0' else False
        sort_key, sort = SearchSetting.get_default_sort(
            current_app.config['WEKO_SEARCH_TYPE_INDEX'], root_flag)
        sort_obj = dict()
        key_fileds = SearchSetting.get_sort_key(sort_key)

        if 'custom_sort' not in sort_key:
            if sort == 'desc':
                sort_obj[key_fileds] = dict(order='desc', unmapped_type='long')
                sort_key = '-' + sort_key
            else:
                sort_obj[key_fileds] = dict(order='asc', unmapped_type='long')
            search._sort.append(sort_obj)
        else:
            ind_id = request.values.get('q', '')
            if sort == 'desc':
                script_str, default_sort = SearchSetting.get_custom_sort(
                    ind_id, 'desc')
                sort_key = '-' + sort_key
            else:
                script_str, default_sort = SearchSetting.get_custom_sort(
                    ind_id, 'asc')

            search._sort = []
            search._sort.append(script_str)
            search._sort.append(default_sort)

        urlkwargs.add('sort', sort_key)

    urlkwargs.add('q', query_q)

    return search, urlkwargs


def check_admin_user():
    """
    Check administrator role user.

    :return: result
    """
    result = True
    user_id = current_user.get_id() \
        if current_user and current_user.is_authenticated else None

    if user_id:
        users = current_app.config['WEKO_PERMISSION_ROLE_USER']

        for lst in list(current_user.roles or []):

            # if is administrator
            if lst.name == users[2]:
                result = True

    return user_id, result


weko_search_factory = item_path_search_factory
es_search_factory = default_search_factory


def opensearch_factory(self, search, query_parser=None):
    """Factory for opensearch.

    :param self:
    :param search:
    :param query_parser:
    :return:
    """
    index_id = request.values.get('index_id')
    search_type = config.WEKO_SEARCH_TYPE_DICT['FULL_TEXT']

    if index_id:
        return item_path_search_factory(self,
                                        search,
                                        index_id=index_id)
    else:
        return default_search_factory(self,
                                      search,
                                      query_parser,
                                      search_type=search_type)


def item_search_factory(self,
                        search,
                        start_date,
                        end_date,
                        list_index_id=None,
                        ignore_publish_status=False):
    """Factory for opensearch.

    :param self:
    :param search: Record Search's instance
    :param start_date: Start date for search
    :param end_date: End date for search
    :param list_index_id: index tree list or None
    :param ignore_publish_status: both public and private
    :return:
    """
    def _get_query(start_term, end_term, indexes):
        query_string = "_type:{} AND " \
                       "relation_version_is_last:true AND " \
                       "publish_date:[{} TO {}]".format(current_app.config[
                           "INDEXER_DEFAULT_DOC_TYPE"],
                           start_term,
                           end_term)
        if not ignore_publish_status:
            query_string += " AND publish_status:0 "
        query_filter = []

        if indexes:

            for index in indexes:
                q_wildcard = {
                    "wildcard": {
                        "path": index
                    }
                }
                query_filter.append(q_wildcard)

        query_q = {
            "size": 10000,
            "query": {
                "bool": {
                    "must": [
                        {
                            "query_string": {
                                "query": query_string
                            }
                        },
                        {
                            "bool": {
                                "should": query_filter
                            }
                        }
                    ]
                }
            },
            "sort":
                [
                    {
                        "publish_date":
                            {
                                "order": "desc"
                            }
                    }
            ]
        }
        return query_q

    query_q = _get_query(start_date, end_date, list_index_id)
    urlkwargs = MultiDict()

    try:
        extr = search._extra.copy()
        search.update_from_dict(query_q)
        search._extra.update(extr)
    except SyntaxError:
        current_app.logger.debug(
            "Failed parsing query: {0}".format(query_q),
            exc_info=True)
        raise InvalidQueryRESTError()

    return search, urlkwargs


def feedback_email_search_factory(self, search):
    """Factory for search feedback email list.

    :param self:
    :param search:
    :return:
    """
    def _get_query():
        query_string = "_type:{} AND " \
                       "relation_version_is_last:true " \
            .format(current_app.config['INDEXER_DEFAULT_DOC_TYPE'])
        query_q = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "feedback_mail_list",
                                "query": {
                                    "bool": {
                                        "must": [
                                            {
                                                "exists": {
                                                    "field": "feedback_mail_list.email"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        {
                            "query_string": {
                                "query": query_string
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "feedback_mail_list": {
                    "nested": {
                        "path": "feedback_mail_list"
                    },
                    "aggs": {
                        "email_list": {
                            "terms": {
                                "field": "feedback_mail_list.email",
                                "size": config.WEKO_SEARCH_MAX_FEEDBACK_MAIL
                            },
                            "aggs": {
                                "top_tag_hits": {
                                    "top_hits": {}
                                }
                            }
                        }
                    }
                }
            }
        }
        return query_q

    query_q = _get_query()

    try:
        # Aggregations.
        extr = search._extra.copy()
        search.update_from_dict(query_q)
        search._extra.update(extr)
    except SyntaxError:
        current_app.logger.debug(
            "Failed parsing query: {0}".format(query_q),
            exc_info=True)
        raise InvalidQueryRESTError()

    return search
