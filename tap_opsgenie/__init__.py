#!/usr/bin/env python3

import datetime
import json
import os
import sys

import backoff
import pendulum
import pytz
import requests
import singer
from singer import Transformer, utils, Schema, get_bookmark, write_bookmark
from singer.catalog import CatalogEntry, Catalog
from strict_rfc3339 import rfc3339_to_timestamp

REQUIRED_CONFIG_KEYS = ["api_token", "query", "start_date"]
STATE = {}
LOGGER = singer.get_logger()
SESSION = requests.Session()


def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


def load_schemas():
    """ Load schemas from schemas folder """
    schemas = {}
    for filename in os.listdir(get_abs_path('schemas')):
        path = get_abs_path('schemas') + '/' + filename
        file_raw = filename.replace('.json', '')
        with open(path) as file:
            schemas[file_raw] = Schema.from_dict(json.load(file))
    return schemas


SCHEMAS = {
    'alerts': {
        'replication_key': 'updatedAt',
        'key_properties': ['tinyId'],
        'replication_method': 'INCREMENTAL'
    }
}


def get_value(stream_id, key, default=None):
    if stream_id not in SCHEMAS:
        return default
    if key not in SCHEMAS[stream_id]:
        return default
    return SCHEMAS[stream_id][key]


def discover():
    raw_schemas = load_schemas()
    streams = []
    for stream_id, schema in raw_schemas.items():
        stream_metadata = []
        streams.append(
            CatalogEntry(
                tap_stream_id=stream_id,
                stream=stream_id,
                schema=schema,
                key_properties=get_value(stream_id, 'key_properties', list()),
                metadata=stream_metadata,
                replication_key=get_value(stream_id, 'replication_key'),
                is_view=None,
                database=None,
                table=None,
                row_count=None,
                stream_alias=None,
                replication_method=get_value(stream_id, 'replication_method'),
            )
        )
    return Catalog(streams)


@backoff.on_exception(backoff.expo,
                      (requests.exceptions.RequestException),
                      max_tries=5,
                      giveup=lambda e: e.response is not None and 400 <= e.response.status_code < 500, # pylint: disable=line-too-long
                      factor=2)
def request(config, url, params=None):
    params = params or {}

    headers = {}
    headers['Authorization'] = 'GenieKey {}'.format(config['api_token'])
    if 'user_agent' in config:
        headers['User-Agent'] = config['user_agent']

    req = requests.Request('GET', url, params=params, headers=headers).prepare()
    LOGGER.info("GET {}".format(req.url))
    resp = SESSION.send(req)

    if resp.status_code >= 400:
        LOGGER.critical(
            "Error making request to OpsGenie API: GET {} [{} - {}]".format(
                req.url, resp.status_code, resp.content))
        sys.exit(1)

    return resp


def format_timestamp(data, typ, schema):
    result = data
    if typ == 'string' and schema.get('format') == 'date-time':
        rfc3339_ts = rfc3339_to_timestamp(data)
        utc_dt = datetime.datetime.utcfromtimestamp(rfc3339_ts).replace(tzinfo=pytz.UTC)
        result = utils.strftime(utc_dt)

    return result


def sync_alerts(config, bookmark):
    url = config['api_url'] + '/alerts'

    ts = pendulum.parse(bookmark).int_timestamp
    query = '{} updatedAt>{}'.format(config['query'], ts)

    params = {
        'query': query,
        'offset': 0,
        'limit': 100,
        'sort': 'updatedAt',
        'order': 'asc'
    }
    resp = request(config, url, params)
    next_page = resp.headers.get('X-Paging-Next', None)
    LOGGER.info(f'Next Page: {next_page}')

    for row in resp.json()['data']:
        yield row

    while next_page:
        resp = request(config, next_page)
        for row in resp.json()['data']:
            yield row
        next_page = resp.headers.get('X-Paging-Next', None)
        LOGGER.info(f'Next Page: {next_page}')


def persist_state(filename, state):
    with open(filename, 'w+') as f:
        json.dump(state, f, indent=2)


def sync(config, state, catalog, args):
    for stream in catalog.get_selected_streams(state):
        LOGGER.info("Syncing stream:" + stream.tap_stream_id)

        singer.write_schema(
            stream_name=stream.tap_stream_id,
            schema=stream.schema.to_dict(),
            key_properties=stream.key_properties,
        )

        current_bookmark = get_bookmark(state, stream.tap_stream_id, 'updatedAt', config['start_date'])
        new_bookmark = pendulum.now().to_iso8601_string()
        LOGGER.info(f'Syncing from {current_bookmark}')
        LOGGER.info(f'Syncing up to {new_bookmark}')

        with Transformer(pre_hook=format_timestamp) as transformer:
            for row in sync_alerts(config, current_bookmark):
                row = transformer.transform(row, stream.schema.to_dict())
                singer.write_records(stream.tap_stream_id, [row])
        write_bookmark(state, stream.tap_stream_id, 'updatedAt', new_bookmark)
        persist_state(args.state_path, state)
    return


@utils.handle_top_exception(LOGGER)
def main():
    # Parse command line arguments
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)

    # If discover flag was passed, run discovery mode and dump output to stdout
    if args.discover:
        catalog = discover()
        catalog.dump()
    # Otherwise run in sync mode
    else:
        if args.catalog:
            catalog = args.catalog
        else:
            catalog = discover()
        sync(args.config, args.state, catalog, args)


if __name__ == "__main__":
    main()