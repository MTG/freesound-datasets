from django.conf import settings
import json
import redis
import time


TIMESTAMP_FIELDNAME = 'redis_timestamp'


class RedisStore(object):

    r = None
    verbose = None

    def __init__(self, verbose=False):
        self.r = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        self.verbose = verbose

    def set(self, key, data):
        data.update({TIMESTAMP_FIELDNAME: int(time.time())})
        self.r.set(key, json.dumps(data))
        if self.verbose:
            print('Set data at key {0}'.format(key))

    def get(self, key, include_elapsed_time=False):
        data = self.r.get(key)
        if data is None:
            if self.verbose:
                print('Getting data from key {0} (it was empty)'.format(key))
            if not include_elapsed_time:
                return {}
            else:
                return {}, 9999999999  # Magic number that will be bigger than any "cache" time (in seconds)

        if self.verbose:
            print('Getting data from key {0}'.format(key))
        data = json.loads(data.decode("utf-8"))
        if not include_elapsed_time:
            return data
        else:
            return data, time.time() - int(data.get(TIMESTAMP_FIELDNAME, time.time()))

    def delete(self, key):
        if self.verbose:
            print('Deleting data at key {0}'.format(key))
        self.r.delete(key)

    def delete_keys(self, pattern='*'):
        if self.verbose:
            print('Deleting keys that match pattern: {0}'.format(pattern))
        count = 0
        for key in self.r.keys(pattern):
            self.r.delete(key)
            count += 1
        return count

store = RedisStore(verbose=False)


DATASET_BASIC_STATS_KEY_TEMPLATE = 'dataset_basic_stats_{0}'
DATASET_TAXONOMY_STATS_KEY_TEMPLATE = 'dataset_taxonomy_stats_{0}'
DATASET_ANNOTATORS_RANKING_TEMPLATE = 'dataset_annotators_ranking_{0}'
DATASET_TOP_CONTRIBUTED_CATEGORIES = 'dataset_top_contributed_categories_{0}'
