#!/usr/bin/python2
""" """
__author__ = 'Jan Klopper (jan@underdark.nl)'
__version__ = 0.1

from uweb3 import model


def ClearCache():
  return {'_stats': {'records': 0, 'hits': 0, 'queries': []}, '_todo': {}}


def CleanCache(cache):
  """This cleans up the cache, manually removing any circular references that
  throw a spanner in the works of the garbage collector and thus avoiding a
  memory leak."""

  def _cleanitem(item):
    cleanups = 0
    # remove reference to connection
    if hasattr(item, 'connection'):
      del item.connection
    # get the raw values to avoid touching __getitem__ which would deepload more items
    for key, value in list(super(model.Record, item).items()):
      if isinstance(value, model.Record):
        # if item has a reference to another item, delete it
        cleanups += _cleanitem(value)
        del item[key]
        cleanups += 1
    return cleanups

  cleanups = 0
  for objtype in cache:
    if not objtype.startswith('_'):
      for item in list(cache[objtype].keys()):
        cleanups += _cleanitem(cache[objtype][item])
        del cache[objtype][item]
  return cleanups


class Record(model.Record):
  """This adds caching to the database model, Specifically FromPrimary and List
  calls are cached, and lookups through the Get method on List calls will be
  pre-warmed to make sure we minimize on SQL queries when looking up
  child-relations.

  The global modelcache variable will hold all the cached data, and a _stats key
  will present keeping track of the amount of queries, cache hits and records.
  """
  lazyload = True

  @staticmethod
  def _addToCache(tblname, key, obj):
    if tblname not in obj.connection.modelcache:
      obj.connection.modelcache[tblname] = {}
    if key not in obj.connection.modelcache[tblname]:
      obj.connection.modelcache[tblname][key] = obj
      return True
    return False

  @classmethod
  def FromPrimary(cls, *args, **kwargs):
    tblname = cls.TableName()
    connection = args[0]
    pkey = (kwargs['pkey_value'] if 'pkey_value' in kwargs else args[1])
    if hasattr(pkey, '_PRIMARY_KEY'):
      pkey = pkey[pkey._PRIMARY_KEY]
    cache = connection.modelcache
    if tblname in cache:
      if pkey in cache[tblname]:
        cache[tblname][pkey]._fromcache = True
        cache['_stats']['hits'] += 1
        return cache[tblname][pkey]
    # see if we need to do some defered loading:
    if cls.lazyload and tblname in cache['_todo']:
      if type(pkey) is not int:
        childID = connection.EscapeValues(pkey)
      else:
        childID = str(pkey)
      cache['_todo'][tblname].add(childID)
      conditions = '%s in (%s)' % (cls._PRIMARY_KEY, ','.join(
          cache['_todo'][tblname]))
      cache['_todo'][tblname] = set()
      list(cls.List(connection, conditions))
    else:
      count = cls._addToCache(tblname, pkey,
                              super(Record, cls).FromPrimary(*args, **kwargs))
      cache['_stats']['records'] += count
      cache['_stats']['queries'].append('%s fromprimary %r' % (tblname, pkey))
    return cache[tblname][pkey]

  @classmethod
  def List(cls, *args, **kwargs):
    args[0].modelcache['_stats']['queries'].append('%s List' % cls.TableName())
    records = super(Record, cls).List(*args, **kwargs)
    if 'yield_unlimited_total_first' in kwargs and kwargs[
        'yield_unlimited_total_first']:
      return cls._cacheListPreseed(list(records),
                                   yield_unlimited_total_first=True)
    return cls._cacheListPreseed(list(records))

  @classmethod
  def _cacheListPreseed(cls, recordset, yield_unlimited_total_first=False):
    tblname = cls.TableName()
    count = 0
    children = -1
    resultrecords = []  #TODO remove this
    if yield_unlimited_total_first:
      resultrecords.append(recordset[0])
      recordset = recordset[1:]

    if not recordset:
      return resultrecords
    for record in recordset:
      # preseed the childrens class if needed (once)
      if children == -1:
        subtypes = cls._getChildTables(record)
        children = dict((subtype, set()) for subtype in subtypes)
      # per record iterate over all subtypes and collect foreign keys
      for subtype in subtypes:
        if hasattr(cls._SUBTYPES[subtype], '_addToCache') and subtype in list(
            record.keys()):
          childID = record.GetRaw(subtype)
          # see if we need to deep fetch, only fetch those who have not been cached before
          if childID and not isinstance(childID, model.BaseRecord):
            if (subtype not in record.connection.modelcache
                or  # havent seen any of this class before
                childID not in record.connection.modelcache[subtype]
               ):  # havent seen this ID before
              if type(childID) is not int:
                childID = record.connection.EscapeValues(childID)
              else:
                childID = str(
                    childID)  # it will turn into a string for the join anyway
              children[subtype].add(childID)
      count += cls._addToCache(tblname, record.key, record)
      resultrecords.append(record.connection.modelcache[tblname][record.key])
    else:
      record.connection.modelcache['_stats']['records'] += count
      # now do a pre-fetch on all linked items
      todolist = record.connection.modelcache['_todo']
      for subtype in subtypes:
        if subtype in children and children[subtype]:
          if hasattr(cls._SUBTYPES[subtype],
                     'lazyload') and cls._SUBTYPES[subtype].lazyload:
            if subtype not in todolist:
              todolist[subtype] = children[subtype]
            else:
              todolist[subtype] = todolist[subtype].union(children[subtype])
          elif hasattr(cls._SUBTYPES[subtype], '_addToCache'):
            #if issubclass(cls._SUBTYPES[subtype], model.VersionedRecord):
            #  a = cls._SUBTYPES[subtype].__mro__[3]
            #  b = cls._SUBTYPES[subtype].__mro__
            #  list(super(cls._SUBTYPES[subtype], cls._SUBTYPES[subtype].__mro__[3]).List(record.connection, conditions = '%s in (%s)' % (cls._SUBTYPES[subtype]._PRIMARY_KEY,
            #                                                                                               ','.join(children[subtype]))))
            #else:
            list(cls._SUBTYPES[subtype].List(
                record.connection,
                conditions='%s in (%s)' % (cls._SUBTYPES[subtype]._PRIMARY_KEY,
                                           ','.join(children[subtype]))))
    return resultrecords

  @classmethod
  def _getChildTables(cls, obj):
    if not hasattr(cls, '_subtypes'):
      cls._subtypes = (set(obj.keys()) & set(cls._SUBTYPES.keys()))
    return cls._subtypes

  def Delete(self, *args, **kwargs):
    try:
      del (self.connection.modelcache[self.TableName()][self.key])
      self.connection.modelcache['_stats']['records'] -= 1
    except KeyError:
      pass
    return super(Record, self).Delete(*args, **kwargs)
