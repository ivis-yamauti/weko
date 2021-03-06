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

"""Module of weko-items-ui utils.."""

import csv
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
from datetime import datetime
from io import StringIO

import bagit
import redis
from elasticsearch.exceptions import NotFoundError
from flask import abort, current_app, flash, redirect, request, send_file, \
    url_for
from flask_babelex import gettext as _
from flask_login import current_user
from invenio_accounts.models import Role, userrole
from invenio_db import db
from invenio_indexer.api import RecordIndexer
from invenio_records.api import RecordBase
from invenio_search import RecordsSearch
from jsonschema import SchemaError, ValidationError
from simplekv.memory.redisstore import RedisStore
from sqlalchemy import MetaData, Table
from weko_deposit.api import WekoDeposit, WekoRecord
from weko_index_tree.utils import get_index_id
from weko_records.api import ItemTypes
from weko_records.serializers.utils import get_item_type_name
from weko_records_ui.permissions import check_file_download_permission
from weko_search_ui.query import item_search_factory
from weko_user_profiles import UserProfile
from weko_workflow.api import WorkActivity
from weko_workflow.models import Action as _Action


def get_list_username():
    """Get list username.

    Query database to get all available username
    return: list of username
    """
    current_user_id = current_user.get_id()
    user_index = 1
    result = list()
    while True:
        try:
            if not int(current_user_id) == user_index:
                user_info = UserProfile.get_by_userid(user_index)
                result.append(user_info.get_username)
            user_index = user_index + 1
        except Exception as e:
            current_app.logger.error(e)
            break

    return result


def get_list_email():
    """Get list email.

    Query database to get all available email
    return: list of email
    """
    current_user_id = current_user.get_id()
    result = list()
    try:
        metadata = MetaData()
        metadata.reflect(bind=db.engine)
        table_name = 'accounts_user'

        user_table = Table(table_name, metadata)
        record = db.session.query(user_table)

        data = record.all()

        for item in data:
            if not int(current_user_id) == item[0]:
                result.append(item[1])
    except Exception as e:
        result = str(e)

    return result


def get_user_info_by_username(username):
    """Get user information by username.

    Query database to get user id by using username
    Get email from database using user id
    Pack response data: user id, user name, email

    parameter:
        username: The username
    return: response pack
    """
    result = dict()
    try:
        user = UserProfile.get_by_username(username)
        user_id = user.user_id

        metadata = MetaData()
        metadata.reflect(bind=db.engine)
        table_name = 'accounts_user'

        user_table = Table(table_name, metadata)
        record = db.session.query(user_table)

        data = record.all()

        for item in data:
            if item[0] == user_id:
                result['username'] = username
                result['user_id'] = user_id
                result['email'] = item[1]
                return result
        return None
    except Exception as e:
        result['error'] = str(e)


def validate_user(username, email):
    """Validate user information.

    Get user id from database using username
    Get user id from database using email
    Compare 2 user id to validate user information
    Pack responde data:
        results: user information (username, user id, email)
        validation: username is match with email or not
        error: null if no error occurs

    param:
        username: The username
        email: The email
    return: response data
    """
    result = {
        'results': '',
        'validation': False,
        'error': ''
    }
    try:
        user = UserProfile.get_by_username(username)
        user_id = 0

        metadata = MetaData()
        metadata.reflect(bind=db.engine)
        table_name = 'accounts_user'

        user_table = Table(table_name, metadata)
        record = db.session.query(user_table)

        data = record.all()

        for item in data:
            if item[1] == email:
                user_id = item[0]
                break

        if user.user_id == user_id:
            user_info = dict()
            user_info['username'] = username
            user_info['user_id'] = user_id
            user_info['email'] = email
            result['results'] = user_info
            result['validation'] = True
        return result
    except Exception as e:
        result['error'] = str(e)

    return result


def get_user_info_by_email(email):
    """
    Get user information by email.

    Query database to get user id by using email
    Get username from database using user id
    Pack response data: user id, user name, email

    parameter:
        email: The email
    return: response
    """
    result = dict()
    try:
        metadata = MetaData()
        metadata.reflect(bind=db.engine)
        table_name = 'accounts_user'

        user_table = Table(table_name, metadata)
        record = db.session.query(user_table)

        data = record.all()
        for item in data:
            if item[1] == email:
                user = UserProfile.get_by_userid(item[0])
                if user is None:
                    result['username'] = ""
                else:
                    result['username'] = user.get_username
                result['user_id'] = item[0]
                result['email'] = email
                return result
        return None
    except Exception as e:
        result['error'] = str(e)


def get_user_information(user_id):
    """
    Get user information user_id.

    Query database to get email by using user_id
    Get username from database using user id
    Pack response data: user id, user name, email

    parameter:
        user_id: The user_id
    return: response
    """
    result = {
        'username': '',
        'email': ''
    }
    user_info = UserProfile.get_by_userid(user_id)
    if user_info is not None:
        result['username'] = user_info.get_username

    metadata = MetaData()
    metadata.reflect(bind=db.engine)
    table_name = 'accounts_user'

    user_table = Table(table_name, metadata)
    record = db.session.query(user_table)

    data = record.all()

    for item in data:
        if item[0] == user_id:
            result['email'] = item[1]
            return result

    return result


def get_user_permission(user_id):
    """
    Get user permission user_id.

    Compare current id with id of current user
    parameter:
        user_id: The user_id
    return: true if current id is the same with id of current user.
    If not return false
    """
    current_id = current_user.get_id()
    if current_id is None:
        return False
    if str(user_id) == current_id:
        return True
    return False


def get_current_user():
    """
    Get user id of user currently login.

    parameter:
    return: current_id
    """
    current_id = current_user.get_id()
    return current_id


def get_actionid(endpoint):
    """
    Get action_id by action_endpoint.

    parameter:
    return: action_id
    """
    with db.session.no_autoflush:
        action = _Action.query.filter_by(
            action_endpoint=endpoint).one_or_none()
        if action:
            return action.id
        else:
            return None


def parse_ranking_results(results,
                          display_rank,
                          list_name='all',
                          title_key='title',
                          count_key=None,
                          pid_key=None,
                          search_key=None,
                          date_key=None):
    """Parse the raw stats results to be usable by the view."""
    ranking_list = []
    if pid_key:
        url = '../records/{0}'
        key = pid_key
    elif search_key:
        url = '../search?page=1&size=20&search_type=1&q={0}'
        key = search_key
    else:
        url = None

    if date_key == 'create_date':
        data_list = parse_ranking_new_items(results)
        results = dict()
        results['all'] = data_list
    if results and list_name in results:
        rank = 1
        count = 0
        date = ''
        for item in results[list_name]:
            t = {}
            if count_key:
                if not count == int(item[count_key]):
                    rank = len(ranking_list) + 1
                    count = int(item[count_key])
                t['rank'] = rank
                t['count'] = count
            elif date_key:
                new_date = item[date_key]
                if new_date == date:
                    t['date'] = ''
                else:
                    t['date'] = new_date
                    date = new_date
            title = item.get(title_key)
            if title_key == 'user_id':
                user_info = UserProfile.get_by_userid(title)
                if user_info:
                    title = user_info.username
                else:
                    title = 'None'
            t['title'] = title
            t['url'] = url.format(item[key]) if url and key in item else None
            ranking_list.append(t)
            if len(ranking_list) == display_rank:
                break
    return ranking_list


def parse_ranking_new_items(result_data):
    """Parse ranking new items.

    :param result_data: result data
    """
    data_list = list()
    if not result_data or not result_data.get('hits') \
            or not result_data.get('hits').get('hits'):
        return data_list
    for item_data in result_data.get('hits').get('hits'):
        item_created = item_data.get('_source')
        data = dict()
        data['create_date'] = item_created.get('publish_date', '')
        data['pid_value'] = item_created.get('control_number')
        meta_data = item_created.get('_item_metadata')
        item_title = ''
        if isinstance(meta_data, dict):
            item_title = meta_data.get('item_title')
        data['record_name'] = item_title
        data_list.append(data)
    return data_list


def validate_form_input_data(result: dict, item_id: str, data: dict):
    """Validate input data.

    :param result: result dictionary.
    :param item_id: item type identifier.
    :param data: form input data
    """
    item_type = ItemTypes.get_by_id(item_id)
    json_schema = item_type.schema.copy()

    # Remove excluded item in json_schema
    remove_excluded_items_in_json_schema(item_id, json_schema)

    data['$schema'] = json_schema.copy()
    validation_data = RecordBase(data)
    try:
        validation_data.validate()
    except ValidationError as error:
        current_app.logger.error(error)
        result["is_valid"] = False
        if 'required' == error.validator:
            result['error'] = _('Please input all required item.')
        elif 'pattern' == error.validator:
            result['error'] = _('Please input the correct data.')
        else:
            result['error'] = _(error.message)
    except SchemaError as error:
        current_app.logger.error(error)
        result["is_valid"] = False
        result['error'] = 'Schema Error:<br/><br/>' + _(error.message)
    except Exception as ex:
        current_app.logger.error(ex)
        result["is_valid"] = False
        result['error'] = _(error.message)


def update_json_schema_by_activity_id(json_data, activity_id):
    """Update json schema by activity id.

    :param json_data: The json schema
    :param activity_id: Activity ID
    :return: json schema
    """
    sessionstore = RedisStore(redis.StrictRedis.from_url(
        'redis://{host}:{port}/1'.format(
            host=os.getenv('INVENIO_REDIS_HOST', 'localhost'),
            port=os.getenv('INVENIO_REDIS_PORT', '6379'))))
    if not sessionstore.redis.exists(
        'updated_json_schema_{}'.format(activity_id)) \
        and not sessionstore.get(
            'updated_json_schema_{}'.format(activity_id)):
        return None
    session_data = sessionstore.get(
        'updated_json_schema_{}'.format(activity_id))
    error_list = json.loads(session_data.decode('utf-8'))

    if error_list:
        for item in error_list['required']:
            sub_item = item.split('.')
            if len(sub_item) == 1:
                json_data['required'] = sub_item
            else:
                if json_data['properties'][sub_item[0]].get('items'):
                    if not json_data['properties'][sub_item[0]]['items'].get(
                            'required'):
                        json_data['properties'][sub_item[0]][
                            'items']['required'] = []
                    json_data['properties'][sub_item[0]]['items'][
                        'required'].append(sub_item[1])
                else:
                    if not json_data[
                            'properties'][sub_item[0]].get('required'):
                        json_data['properties'][sub_item[0]]['required'] = []
                    json_data['properties'][sub_item[0]]['required'].append(
                        sub_item[1])
        for item in error_list['pattern']:
            sub_item = item.split('.')
            if len(sub_item) == 2:
                creators = json_data['properties'][sub_item[0]].get('items')
                if not creators:
                    break
                for creator in creators.get('properties'):
                    if creators['properties'][creator].get('items'):
                        givename = creators['properties'][creator]['items']
                        if givename['properties'].get(sub_item[1]):
                            if not givename.get('required'):
                                givename['required'] = []
                            givename['required'].append(sub_item[1])
    return json_data


def package_export_file(item_type_data):
    """Export TSV Files.

    Arguments:
        item_type_data  -- schema's Item Type

    Returns:
        return          -- TSV file

    """
    tsv_output = StringIO()
    jsonschema_url = item_type_data.get('root_url') + item_type_data.get(
        'jsonschema')

    tsv_writer = csv.writer(tsv_output, delimiter='\t')
    tsv_writer.writerow(['#ItemType',
                         item_type_data.get('name'),
                         jsonschema_url])

    keys = item_type_data['keys']
    labels = item_type_data['labels']
    tsv_metadata_writer = csv.DictWriter(tsv_output,
                                         fieldnames=keys,
                                         delimiter='\t')
    tsv_metadata_label_writer = csv.DictWriter(tsv_output,
                                               fieldnames=labels,
                                               delimiter='\t')
    tsv_metadata_data_writer = csv.writer(tsv_output,
                                          delimiter='\t')
    tsv_metadata_writer.writeheader()
    tsv_metadata_label_writer.writeheader()
    for recid in item_type_data.get('recids'):
        tsv_metadata_data_writer.writerow(
            [recid, item_type_data.get('root_url') + 'records/' + str(recid)]
            + item_type_data['data'].get(recid)
        )

    return tsv_output


def make_stats_tsv(item_type_id, recids, list_item_role):
    """Prepare TSV data for each Item Types.

    Arguments:
        item_type_id    -- ItemType ID
        recids          -- List records ID
    Returns:
        ret             -- Key properties
        ret_label       -- Label properties
        records.attr_output -- Record data

    """
    item_type = ItemTypes.get_by_id(item_type_id).render
    list_hide = get_item_from_option(item_type_id)
    if hide_meta_data_for_role(
        list_item_role.get(item_type_id)) and item_type and item_type.get(
            'table_row'):
        for name_hide in list_hide:
            item_type['table_row'] = hide_table_row_for_tsv(
                item_type.get('table_row'), name_hide)

    table_row_properties = item_type['table_row_map']['schema'].get(
        'properties')

    class RecordsManager:
        """Management data for exporting records."""

        first_recid = 0
        cur_recid = 0
        filepath_idx = 1
        recids = []
        records = {}
        attr_data = {}
        attr_output = {}

        def __init__(self, record_ids):
            """Class initialization."""
            self.recids = record_ids
            self.first_recid = record_ids[0]
            for record_id in record_ids:
                record = WekoRecord.get_record_by_pid(record_id)
                self.records[record_id] = record
                self.attr_output[record_id] = []

        def get_max_ins(self, attr):
            """Get max data each main property in all exporting records."""
            largest_size = 1
            self.attr_data[attr] = {'max_size': 0}
            for record in self.records:
                if isinstance(self.records[record].get(attr), dict) \
                    and self.records[record].get(attr).get(
                        'attribute_value_mlt'):
                    self.attr_data[attr][record] = self.records[record][attr][
                        'attribute_value_mlt']
                else:
                    if self.records[record].get(attr):
                        self.attr_data[attr][record] = \
                            self.records[record].get(attr)
                    else:
                        self.attr_data[attr][record] = []
                rec_size = len(self.attr_data[attr][record])
                if rec_size > largest_size:
                    largest_size = rec_size
            self.attr_data[attr]['max_size'] = largest_size

            return self.attr_data[attr]['max_size']

        def get_max_items(self, item_attrs):
            """Get max data each sub property in all exporting records."""
            list_attr = item_attrs.split('.')
            max_length = 0
            if len(list_attr) == 1:
                return self.attr_data[item_attrs]['max_size']
            elif len(list_attr) == 2:
                max_length = 1
                first_attr = list_attr[0].split('[')
                item_attr = first_attr[0]
                idx = int(first_attr[1].split(']')[0])
                sub_attr = list_attr[1].split('[')[0]
                for record in self.records:
                    if self.records[record].get(item_attr) \
                        and len(self.records[record][item_attr][
                            'attribute_value_mlt']) > idx \
                        and self.records[record][item_attr][
                            'attribute_value_mlt'][idx].get(sub_attr):
                        cur_len = len(self.records[record][item_attr][
                            'attribute_value_mlt'][idx][sub_attr])
                        if cur_len > max_length:
                            max_length = cur_len
            elif len(list_attr) == 3:
                max_length = 1
                first_attr = list_attr[0].split('[')
                key2 = list_attr[1].split('[')
                item_attr = first_attr[0]
                idx = int(first_attr[1].split(']')[0])
                sub_attr = list_attr[1].split('[')[0]
                idx_2 = int(key2[1].split(']')[0])
                sub_attr_2 = list_attr[2].split('[')[0]
                for record in self.records:
                    if self.records[record].get(item_attr):
                        attr_val = self.records[record][item_attr][
                            'attribute_value_mlt']
                        if len(attr_val) > idx and attr_val[idx].get(sub_attr) \
                            and len(attr_val[idx][sub_attr]) > idx_2 \
                            and attr_val[idx][sub_attr][idx_2].get(
                                sub_attr_2):
                            cur_len = len(attr_val[idx][sub_attr][idx_2][
                                sub_attr_2])
                            if cur_len > max_length:
                                max_length = cur_len
            return max_length

        def get_subs_item(self,
                          item_key,
                          item_label,
                          properties,
                          data=None,
                          is_object=False):
            """Building key, label and data from key properties.

            Arguments:
                item_key    -- Key properties
                item_label  -- Label properties
                properties  -- Data properties
                data        -- Record data
                is_object   -- Is objecting property?
            Returns:
                o_ret       -- Key properties
                o_ret_label -- Label properties
                ret_data    -- Record data

            """
            o_ret = []
            o_ret_label = []
            ret_data = []
            max_items = self.get_max_items(item_key)
            max_items = 1 if is_object else max_items
            for idx in range(max_items):
                key_list = []
                key_label = []
                key_data = []
                for key in sorted(properties):
                    if properties[key]['type'] == 'array':
                        if data and idx < len(data) and data[idx].get(key):
                            m_data = data[idx][key]
                        else:
                            m_data = None
                        sub, sublabel, subdata = self.get_subs_item(
                            '{}[{}].{}'.format(item_key, str(idx), key),
                            '{}#{}.{}'.format(item_label, str(idx + 1),
                                              properties[key].get('title')),
                            properties[key]['items']['properties'],
                            m_data)
                        if is_object:
                            _sub_ = []
                            for item in sub:
                                if 'item_' in item:
                                    _sub_.append(item.split('.')[0].replace(
                                        '[0]', '') + '.' + '.'.join(
                                        item.split('.')[1:]))
                                else:
                                    _sub_.append(item)
                            sub = _sub_
                        key_list.extend(sub)
                        key_label.extend(sublabel)
                        key_data.extend(subdata)
                    else:
                        if isinstance(data, dict):
                            data = [data]
                        if is_object:
                            key_list.append('{}.{}'.format(
                                item_key,
                                key))
                            key_label.append('{}.{}'.format(
                                item_label,
                                properties[key].get('title')))
                        else:
                            key_list.append('{}[{}].{}'.format(
                                item_key,
                                str(idx),
                                key))
                            key_label.append('{}#{}.{}'.format(
                                item_label,
                                str(idx + 1),
                                properties[key].get('title')))
                        if data and idx < len(data) and data[idx].get(key):
                            key_data.append(data[idx][key])
                        else:
                            key_data.append('')

                key_list_len = len(key_list)
                for key_index in range(key_list_len):
                    if 'filename' in key_list[key_index] \
                        or 'thumbnail_label' in key_list[key_index] \
                            and len(item_key.split('.')) == 2:
                        key_list.insert(0, '.file_path#'
                                        + str(self.filepath_idx + idx))
                        key_label.insert(0, '.ファイルパス#'
                                         + str(self.filepath_idx + idx))
                        if key_data[key_index]:
                            key_data.insert(0, 'recid_{}/{}'.format(str(
                                self.cur_recid), key_data[key_index]))
                        else:
                            key_data.insert(0, '')
                        if idx == max_items - 1 \
                                and self.first_recid == self.cur_recid:
                            self.filepath_idx += max_items
                        break

                o_ret.extend(key_list)
                o_ret_label.extend(key_label)
                ret_data.extend(key_data)

            return o_ret, o_ret_label, ret_data

    records = RecordsManager(recids)

    ret = ['#.id', '.uri']
    ret_label = ['#ID', 'URI']

    max_path = records.get_max_ins('path')
    ret.extend(['.metadata.path[{}]'.format(i) for i in range(max_path)])
    ret_label.extend(['.IndexID#{}'.format(i + 1) for i in range(max_path)])
    ret.append('.metadata.pubdate')
    ret_label.append('公開日')

    for recid in recids:
        records.attr_output[recid].extend(records.attr_data['path'][recid])
        records.attr_output[recid].extend([''] * (max_path - len(
            records.attr_output[recid])))
        records.attr_output[recid].append(records.records[recid][
            'pubdate']['attribute_value'])

    for item_key in item_type.get('table_row'):
        item = table_row_properties.get(item_key)
        records.get_max_ins(item_key)
        keys = []
        labels = []
        for recid in recids:
            records.cur_recid = recid
            if item.get('type') == 'array':
                key, label, data = records.get_subs_item(
                    item_key,
                    item.get('title'),
                    item['items']['properties'],
                    records.attr_data[item_key][recid]
                )
                if not keys:
                    keys = key
                if not labels:
                    labels = label
                records.attr_output[recid].extend(data)
            elif item.get('type') == 'object':
                key, label, data = records.get_subs_item(
                    item_key,
                    item.get('title'),
                    item['properties'],
                    records.attr_data[item_key][recid],
                    True
                )
                if not keys:
                    keys = key
                if not labels:
                    labels = label
                records.attr_output[recid].extend(data)
            else:
                if not keys:
                    keys = [item_key]
                if not labels:
                    labels = [item.get('title')]
                data = records.attr_data[item_key].get(recid) or ['']
                records.attr_output[recid].extend(data)

        new_keys = []
        for key in keys:
            if 'file_path' not in key:
                key = '.metadata.{}'.format(key)
            new_keys.append(key)
        ret.extend(new_keys)
        ret_label.extend(labels)

    return ret, ret_label, records.attr_output


def get_list_file_by_record_id(recid):
    """Get file buckets by record id.

    Arguments:
        recid     -- {number} record id.
    Returns:
        list_file  -- list file name of record.

    """
    body = {
        "query": {
            "function_score": {
                "query": {
                    "match": {
                        "_id": recid
                    }
                }
            }
        },
        "_source": ["file"],
        "size": 1
    }
    indexer = RecordIndexer()
    result = indexer.client.search(
        index=current_app.config['INDEXER_DEFAULT_INDEX'],
        body=body
    )
    list_file_name = []

    if isinstance(result, dict) and isinstance(result.get('hits'), dict) and \
            isinstance(result['hits'].get('hits'), list) and \
            len(result['hits']['hits']) > 0 and \
            isinstance(result['hits']['hits'][0], dict) and \
            isinstance(result['hits']['hits'][0].get('_source'), dict) and \
            isinstance(result['hits']['hits'][0]['_source'].get('file'), dict)\
            and result['hits']['hits'][0]['_source']['file'].get('URI'):
        list_file = result['hits']['hits'][0]['_source']['file'].get('URI')

        list_file_name = [
            recid + '/' + item.get('value') for item in list_file]
    return list_file_name


def export_items(post_data):
    """Gather all the item data and export and return as a JSON or BIBTEX.

    :return: JSON, BIBTEX
    """
    def check_item_type_name(name):
        """Check a list of allowed characters in filenames."""
        new_name = re.sub(r'[\/:*"<>|\s]', '_', name)
        return new_name

    include_contents = True if \
        post_data['export_file_contents_radio'] == 'True' else False
    export_format = post_data['export_format_radio']
    record_ids = json.loads(post_data['record_ids'])
    record_metadata = json.loads(post_data['record_metadata'])
    if len(record_ids) > _get_max_export_items():
        return abort(400)
    elif len(record_ids) == 0:
        flash(_('Please select Items to export.'), 'error')
        return redirect(url_for('weko_items_ui.export'))

    result = {'items': []}
    temp_path = tempfile.TemporaryDirectory()
    item_types_data = {}

    try:
        # Set export folder
        export_path = temp_path.name + '/' + \
            datetime.utcnow().strftime("%Y%m%d%H%M%S")
        # Double check for limits
        for record_id in record_ids:
            record_path = export_path + '/recid_' + str(record_id)
            os.makedirs(record_path, exist_ok=True)
            exported_item, list_item_role = _export_item(
                record_id,
                export_format,
                include_contents,
                record_path,
                record_metadata.get(str(record_id))
            )

            result['items'].append(exported_item)

            item_type_id = exported_item.get('item_type_id')
            item_type = ItemTypes.get_by_id(item_type_id)
            if not item_types_data.get(item_type_id):
                item_type_name = check_item_type_name(
                    item_type.item_type_name.name)
                item_types_data[item_type_id] = {
                    'item_type_id': item_type_id,
                    'name': '{}({})'.format(
                        item_type_name,
                        item_type_id),
                    'root_url': request.url_root,
                    'jsonschema': 'items/jsonschema/' + item_type_id,
                    'keys': [],
                    'labels': [],
                    'recids': [],
                    'data': {},
                }
            item_types_data[item_type_id]['recids'].append(record_id)

        # Create export info file
        for item_type_id in item_types_data:
            keys, labels, records = make_stats_tsv(
                item_type_id,
                item_types_data[item_type_id]['recids'],
                list_item_role)
            item_types_data[item_type_id]['recids'].sort()
            item_types_data[item_type_id]['keys'] = keys
            item_types_data[item_type_id]['labels'] = labels
            item_types_data[item_type_id]['data'] = records
            item_type_data = item_types_data[item_type_id]

            with open('{}/{}.tsv'.format(export_path,
                                         item_type_data.get('name')),
                      'w') as file:
                tsvs_output = package_export_file(item_type_data)
                file.write(tsvs_output.getvalue())

        # Create bag
        bagit.make_bag(export_path)
        # Create download file
        shutil.make_archive(export_path, 'zip', export_path)
    except Exception:
        current_app.logger.error('-' * 60)
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error('-' * 60)
        flash(_('Error occurred during item export.'), 'error')
        return redirect(url_for('weko_items_ui.export'))
    return send_file(export_path + '.zip')


def export_item_custorm(post_data):
    """Gather all the item data and export and return as a JSON or BIBTEX.

    :return: JSON, BIBTEX
    """
    include_contents = True
    record_id = post_data['record_id']

    result = {'items': []}
    temp_path = tempfile.TemporaryDirectory()
    item_types_data = {}

    try:
        # Set export folder
        export_path = temp_path.name + '/' + datetime.utcnow().strftime(
            "%Y%m%d%H%M%S")
        # Double check for limits
        record_path = export_path + '/recid_' + str(record_id)
        os.makedirs(record_path, exist_ok=True)
        exported_item, list_item_role = _export_item(
            record_id,
            None,
            include_contents,
            record_path,
        )

        result['items'].append(exported_item)

        item_type_id = exported_item.get('item_type_id')
        item_type = ItemTypes.get_by_id(item_type_id)
        if not item_types_data.get(item_type_id):
            item_types_data[item_type_id] = {}

            item_types_data[item_type_id] = {
                'item_type_id': item_type_id,
                'name': '{}({})'.format(
                    item_type.item_type_name.name,
                    item_type_id),
                'root_url': request.url_root,
                'jsonschema': 'items/jsonschema/' + item_type_id,
                'keys': [],
                'labels': [],
                'recids': [],
                'data': {},
            }
        item_types_data[item_type_id]['recids'].append(record_id)

        # Create export info file
        for item_type_id in item_types_data:
            keys, labels, records = make_stats_tsv(
                item_type_id,
                item_types_data[item_type_id]['recids'],
                list_item_role)
            item_types_data[item_type_id]['recids'].sort()
            item_types_data[item_type_id]['keys'] = keys
            item_types_data[item_type_id]['labels'] = labels
            item_types_data[item_type_id]['data'] = records
            item_type_data = item_types_data[item_type_id]

            with open('{}/{}.tsv'.format(export_path,
                                         item_type_data.get('name')),
                      'w') as file:
                tsvs_output = package_export_file(item_type_data)
                file.write(tsvs_output.getvalue())

        # Create bag
        bagit.make_bag(export_path)
        # Create download file
        shutil.make_archive(export_path, 'zip', export_path)
    except Exception:
        current_app.logger.error('-' * 60)
        traceback.print_exc(file=sys.stdout)
        current_app.logger.error('-' * 60)
    return send_file(export_path + '.zip')


def _get_max_export_items():
    """Get max amount of items to export."""
    max_table = current_app.config['WEKO_ITEMS_UI_MAX_EXPORT_NUM_PER_ROLE']
    non_user_max = max_table[current_app.config[
        'WEKO_PERMISSION_ROLE_GENERAL']]
    current_user_id = current_user.get_id()

    if not current_user_id:  # Non-logged in users
        return non_user_max

    try:
        roles = db.session.query(Role).join(userrole).filter_by(
            user_id=current_user_id).all()
    except Exception:
        return current_app.config['WEKO_ITEMS_UI_DEFAULT_MAX_EXPORT_NUM']

    current_max = non_user_max
    for role in roles:
        if role in max_table and max_table[role] > current_max:
            current_max = max_table[role]
    return current_max


def _export_item(record_id,
                 export_format,
                 include_contents,
                 tmp_path=None,
                 records_data=None):
    """Exports files for record according to view permissions."""
    exported_item = {}
    record = WekoRecord.get_record_by_pid(record_id)
    list_item_role = {}
    if record:
        exported_item['record_id'] = record.id
        exported_item['name'] = 'recid_{}'.format(record_id)
        exported_item['files'] = []
        exported_item['path'] = 'recid_' + str(record_id)
        exported_item['item_type_id'] = record.get('item_type_id')
        if not records_data:
            records_data = record
        if exported_item['item_type_id']:
            list_hidden = get_ignore_item_from_mapping(
                exported_item['item_type_id'])
            if records_data.get('metadata'):
                meta_data = records_data.get('metadata')
                record_role_ids = {
                    'weko_creator_id': meta_data.get('weko_creator_id'),
                    'weko_shared_id': meta_data.get('weko_shared_id')
                }
                list_item_role.update(
                    {exported_item['item_type_id']: record_role_ids})
                if hide_meta_data_for_role(record_role_ids):
                    for hide_key in list_hidden:
                        if meta_data.get(hide_key):
                            del records_data['metadata'][hide_key]

        # Create metadata file.
        with open('{}/{}_metadata.json'.format(tmp_path,
                                               exported_item['name']),
                  'w',
                  encoding='utf8') as output_file:
            json.dump(records_data, output_file, indent=2,
                      sort_keys=True, ensure_ascii=False)
        # First get all of the files, checking for permissions while doing so
        if include_contents:
            # Get files
            for file in record.files:  # TODO: Temporary processing
                if check_file_download_permission(record, file.info()):
                    if ('accessrole' in file.info() and file.info()[
                            'accessrole'] != 'open_restricted'):
                        exported_item['files'].append(file.info())
                        # TODO: Then convert the item into the desired format
                        if file:
                            shutil.copy2(file.obj.file.uri,
                                         tmp_path + '/' + file.obj.basename)

    return exported_item, list_item_role


def get_new_items_by_date(start_date: str, end_date: str) -> dict:
    """Get ranking new item by date.

    :param start_date:
    :param end_date:
    :return:
    """
    record_search = RecordsSearch(
        index=current_app.config['SEARCH_UI_SEARCH_INDEX'])
    result = dict()

    try:
        search_instance, _qs_kwargs = item_search_factory(None,
                                                          record_search,
                                                          start_date,
                                                          end_date)
        search_result = search_instance.execute()
        result = search_result.to_dict()
    except NotFoundError as e:
        current_app.logger.debug("Indexes do not exist yet: ", str(e))

    return result


def update_schema_remove_hidden_item(schema, render, items_name):
    """Update schema: remove hidden items.

    :param schema: json schema
    :param render: json render
    :param items_name: list items which has hidden flg
    :return: The json object.
    """
    for item in items_name:
        hidden_flg = False
        key = schema[item]['key']
        if render['meta_list'].get(key):
            hidden_flg = render['meta_list'][key]['option']['hidden']
        if render.get('meta_system') and render['meta_system'].get(key):
            hidden_flg = render['meta_system'][key]['option']['hidden']
        if hidden_flg:
            schema[item]['condition'] = 1

    return schema


def to_files_js(record):
    """List files in a deposit."""
    res = []
    files = record.files
    if files is not None:
        for f in files:
            res.append({
                'displaytype': f.get('displaytype', ''),
                'filename': f.get('filename', ''),
                'mimetype': f.mimetype,
                'licensetype': f.get('licensetype', ''),
                'key': f.key,
                'version_id': str(f.version_id),
                'checksum': f.file.checksum,
                'size': f.file.size,
                'completed': True,
                'progress': 100,
                'links': {
                    'self': (
                        current_app.config['DEPOSIT_FILES_API']
                        + u'/{bucket}/{key}?versionId={version_id}'.format(
                            bucket=f.bucket_id,
                            key=f.key,
                            version_id=f.version_id,
                        )),
                },
                'is_show': f.is_show,
                'is_thumbnail': f.is_thumbnail
            })

    return res


def update_sub_items_by_user_role(item_type_id, schema_form):
    """Update sub item by user role.

    @param item_type_id:
    @param schema_form:
    @return:
    """
    item_type_name = get_item_type_name(item_type_id)
    excluded_sub_items = get_excluded_sub_items(item_type_name)
    excluded_forms = []
    for form in schema_form:
        if "title_{}".format(form.get('title')).lower() in excluded_sub_items:
            excluded_forms.append(form)
        elif form.get('items') and \
                form['items'][0]['key'].split('.')[1] in excluded_sub_items:
            excluded_forms.append(form)
    for item in excluded_forms:
        schema_form.remove(item)


def remove_excluded_items_in_json_schema(item_id, json_schema):
    """Remove excluded items in json_schema.

    :item_id: object
    :json_schema: object
    """
    # Check role for input(5 item type)
    item_type_name = get_item_type_name(item_id)
    excluded_sub_items = get_excluded_sub_items(item_type_name)
    if len(excluded_sub_items) == 0:
        return
    """ Check excluded sub item name which exist in json_schema """
    """     Case exist => add sub item to array """
    properties = json_schema.get('properties')
    removed_json_schema = []
    if properties:
        for pro in properties:
            pro_val = properties.get(pro)
            sub_pro = pro_val.get('properties')
            if pro_val and sub_pro:
                for sub_item in excluded_sub_items:
                    sub_property = sub_pro.get(sub_item)
                    if sub_property:
                        removed_json_schema.append(pro)
    """ If sub item array have data, we remove sub items im json_schema """
    if len(removed_json_schema) > 0:
        for item in removed_json_schema:
            if properties.get(item):
                del properties[item]


def get_excluded_sub_items(item_type_name):
    """Get excluded sub items by role.

    :item_type_name: object
    """
    usage_application_item_type = current_app.config.get(
        'WEKO_ITEMS_UI_USAGE_APPLICATION_ITEM_TYPE')
    if (not usage_application_item_type or not isinstance(
            usage_application_item_type, dict)):
        return []
    current_user_role = get_current_user_role()
    item_type_role = []
    item_type = usage_application_item_type.get(item_type_name.strip())
    if current_user_role and item_type and item_type.get(
            current_user_role.name):
        item_type_role = item_type.get(current_user_role.name)
    return item_type_role


def get_current_user_role():
    """Get current user roles."""
    current_user_role = ''
    for role in current_user.roles:
        if role in current_app.config['WEKO_USERPROFILES_ROLES']:
            current_user_role = role
            break
    return current_user_role


def is_need_to_show_agreement_page(item_type_name):
    """Check need to show Terms and Conditions or not."""
    current_user_role = get_current_user_role()
    general_role = current_app.config['WEKO_USERPROFILES_GENERAL_ROLE']
    item_type_list = current_app.config[
        'WEKO_ITEMS_UI_LIST_ITEM_TYPE_NOT_NEED_AGREE']
    if (current_user_role == general_role
            and item_type_name in item_type_list):
        return False
    return True


def update_index_tree_for_record(pid_value, index_tree_id):
    """Update index tree for record.

    :param index_tree_id:
    :param pid_value: pid value to get record and WekoDeposit
    :return:True set successfully otherwise False
    """
    list_index = []
    list_index.append(index_tree_id)
    data = {"index": list_index}
    record = WekoRecord.get_record_by_pid(pid_value)
    deposit = WekoDeposit(record, record.model)
    # deposit.clear()
    deposit.update(data)
    deposit.commit()
    db.session.commit()


def validate_user_mail(email):
    """Validate user mail.

    @param email:
    @return:
    """
    result = {}
    try:
        if email != '':
            result = {'results': '',
                      'validation': '',
                      'error': ''
                      }
            user_info = get_user_info_by_email(
                email)
            if user_info and user_info.get(
                    'user_id') is not None:
                if int(user_info.get('user_id')) == int(current_user.get_id()):
                    result['validation'] = False
                    result['error'] = _(
                        "You cannot specify "
                        "yourself in approval lists setting.")
                else:
                    result['results'] = user_info
                    result['validation'] = True
            else:
                result['validation'] = False
    except Exception as ex:
        result['error'] = str(ex)

    return result


def update_action_handler(activity_id, action_id, user_id):
    """Update action handler for each action of activity.

    :param activity_id:
    :param action_id:
    :param user_id:
    :return:
    """
    from weko_workflow.models import ActivityAction
    with db.session.begin_nested():
        activity_action = ActivityAction.query.filter_by(
            activity_id=activity_id,
            action_id=action_id, ).one_or_none()
        if activity_action:
            activity_action.action_handler = user_id
            db.session.merge(activity_action)
    db.session.commit()


def validate_user_mail_and_index(request_data):
    """Validate user's mail,index tree.

    :param request_data:
    :return:
    """
    users = request_data.get('user_to_check', [])
    auto_set_index_action = request_data.get('auto_set_index_action', False)
    activity_id = request_data.get('activity_id')
    result = {
        "index": True
    }
    try:
        for user in users:
            user_obj = request_data.get(user)
            email = user_obj.get('mail')
            validation_result = validate_user_mail(email)
            if validation_result.get('validation') is True:
                update_action_handler(activity_id, user_obj.get('action_id'),
                                      validation_result.get('results').get(
                                          'user_id'))
            result[user] = validation_result
        if auto_set_index_action is True:
            is_existed_valid_index_tree_id = True if \
                get_index_id(activity_id) else False
            result['index'] = is_existed_valid_index_tree_id
    except Exception as ex:
        import traceback
        traceback.print_exc()
        result['error'] = str(ex)
    return result


def recursive_form(schema_form):
    """
    Recur the all the child form to set value for specific property.

    :param schema_form:
    :return: from result
    """
    for form in schema_form:
        if 'items' in form:
            recursive_form(form.get('items', []))
        # Set value for titleMap of select in case of position
        # and select format
        if (form.get('title', '') == 'Position' and form.get('type', '')
                == 'select'):
            dict_data = []
            positions = current_app.config.get(
                'WEKO_USERPROFILES_POSITION_LIST')
            for val in positions:
                if val[0]:
                    current_position = {
                        "value": val[0],
                        "name": str(val[1])
                    }
                    dict_data.append(current_position)
                    form['titleMap'] = dict_data


def set_multi_language_name(item, cur_lang):
    """Set multi language name: Get corresponding language and set to json.

    :param item: json object
    :param cur_lang: current language
    :return: The modified json object.
    """
    if 'titleMap' in item:
        for value in item['titleMap']:
            if 'name_i18n' in value \
                    and len(value['name_i18n'][cur_lang]) > 0:
                value['name'] = value['name_i18n'][cur_lang]


def validate_save_title_and_share_user_id(result, data):
    """Save title and shared user id for activity.

    :param result: json object
    :param data: json object
    :return: The result.
    """
    try:
        if data and isinstance(data, dict):
            activity_id = data['activity_id']
            title = data['title']
            shared_user_id = data['shared_user_id']
            activity = WorkActivity()
            activity.update_title_and_shared_user_id(activity_id, title,
                                                     shared_user_id)
    except Exception as ex:
        result['is_valid'] = False
        result['error'] = str(ex)
    return result


def get_data_authors_prefix_settings():
    """Get all authors prefix settings."""
    from weko_authors.models import AuthorsPrefixSettings
    try:
        return db.session.query(AuthorsPrefixSettings).all()
    except Exception as e:
        current_app.logger.error(e)
        return None


def hide_meta_data_for_role(record):
    """
    Show hide metadate for curent user role.

    :return:
    """
    is_hidden = True

    # Admin users
    supers = current_app.config['WEKO_PERMISSION_SUPER_ROLE_USER']
    for role in list(current_user.roles or []):
        if role.name in supers:
            is_hidden = False
            break
    # Community users
    community_role_name = current_app.config[
        'WEKO_PERMISSION_ROLE_COMMUNITY']
    for role in list(current_user.roles or []):
        if role.name in community_role_name:
            is_hidden = False
            break
    if record:
        # Item Register users
        if record.get('weko_creator_id') in list(current_user.roles or []):
            is_hidden = False

        # Share users
        if record.get('weko_shared_id') in list(current_user.roles or []):
            is_hidden = False

    return is_hidden


def get_ignore_item_from_mapping(_item_type_id):
    """Get ignore item from mapping.

    :param _item_type_id:
    :return ignore_list:
    """
    ignore_list = []
    meta_options, item_type_mapping = get_options_and_order_list(_item_type_id)
    for key, val in meta_options.items():
        hidden = val.get('option').get('hidden')
        if hidden:
            ignore_list.append(
                get_mapping_name_item_type_by_key(key, item_type_mapping))
    return ignore_list


def get_mapping_name_item_type_by_key(key, item_type_mapping):
    """Get mapping name item type by key.

    :param item_type_mapping:
    :param key:
    :return: name
    """
    for mapping_key in item_type_mapping:
        if mapping_key == key:
            property_data = item_type_mapping.get(mapping_key)
            if isinstance(property_data.get('jpcoar_mapping'), dict):
                for name in property_data.get('jpcoar_mapping'):
                    return name
    return key


def get_item_from_option(_item_type_id):
    """Get all keys of properties that is set Hide option on metadata."""
    ignore_list = []
    meta_options = get_options_list(_item_type_id)
    for key, val in meta_options.items():
        hidden = val.get('option').get('hidden')
        if hidden:
            ignore_list.append(key)
    return ignore_list


def get_options_list(item_type_id):
    """Get Options by item type id.

    :param item_type_id:
    :return: options dict
    """
    json_item = ItemTypes.get_record(item_type_id)
    meta_options = json_item.model.render.get('meta_fix')
    meta_options.update(json_item.model.render.get('meta_list'))
    return meta_options


def get_options_and_order_list(item_type_id):
    """Get Options by item type id.

    :param item_type_id:
    :return: options dict and item type mapping
    """
    from weko_records.api import Mapping
    meta_options = get_options_list(item_type_id)
    item_type_mapping = Mapping.get_record(item_type_id)
    return meta_options, item_type_mapping


def hide_table_row_for_tsv(table_row, hide_key):
    """Get Options by item type id.

    :param hide_key:
    :param table_row:
    :return: table_row
    """
    for key in table_row:
        if key == hide_key:
            del table_row[table_row.index(hide_key)]
    return table_row


def is_schema_include_key(schema):
    """Check if schema have filename/billing_filename key."""
    properties = schema.get('properties')
    need_file = False
    need_billing_file = False
    for key in properties:
        item = properties.get(key)
        # Do check for object type
        if 'properties' in item:
            object = item.get('properties')
            if 'is_billing' in object and 'filename' in object:
                need_billing_file = True
            if 'is_billing' not in object and 'filename' in object:
                need_file = True
        # Do check for array/multiple type
        elif 'items' in item:
            object = item.get('items').get('properties')
            if 'is_billing' in object and 'filename' in object:
                need_billing_file = True
            if 'is_billing' not in object and 'filename' in object:
                need_file = True
    return need_file, need_billing_file


def isExistKeyInDict(_key, _dict):
    """Check key exist in dict and value of key is dict type.

    :param _key: key in dict.
    :param _dict: dict.
    :return: if key exist and value of this key is dict type => return True
    else False.
    """
    return isinstance(_dict, dict) and isinstance(_dict.get(_key), dict)


def set_validation_message(item, cur_lang):
    """Set validation message.

    :param item: json of control (ex: json of text input).
    :param cur_lang: current language.
    :return: item, set validationMessage attribute for item.
    """
    i18n = 'validationMessage_i18n'
    message_attr = 'validationMessage'
    if i18n in item and cur_lang:
        item[message_attr] = item[i18n][cur_lang]


def translate_validation_message(item_property, cur_lang):
    """Recursive in order to set translate language validation message.

    :param item_property: .
    :param cur_lang: .
    :return: .
    """
    items_attr = 'items'
    properties_attr = 'properties'
    if isExistKeyInDict(items_attr, item_property):
        for _key1, value1 in item_property.get(items_attr).items():
            if not type(value1) is dict:
                continue
            for _key2, value2 in value1.items():
                set_validation_message(value2, cur_lang)
                translate_validation_message(value2, cur_lang)
    if isExistKeyInDict(properties_attr, item_property):
        for _key, value in item_property.get(properties_attr).items():
            set_validation_message(value, cur_lang)
            translate_validation_message(value, cur_lang)
