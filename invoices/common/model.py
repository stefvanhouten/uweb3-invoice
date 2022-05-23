from uweb3 import model


class RichVersionedRecord(model.VersionedRecord):
    """Provides a richer uweb VersionedRecord class."""

    SEARCHABLE_COLUMNS = []

    @classmethod
    def List(
        cls,
        connection,
        conditions=None,
        limit=None,
        offset=None,
        order=None,
        yield_unlimited_total_first=False,
        search=None,
        tables=None,
        escape=True,
        fields=None,
    ):
        """Yields the latest Record for each versioned entry in the table.

        Arguments:
        @ connection: object
          Database connection to use.
        % conditions: str / iterable ~~ None
          Optional query portion that will be used to limit the list of results.
          If multiple conditions are provided, they are joined on an 'AND' string.
        % limit: int ~~ None
          Specifies a maximum number of items to be yielded. The limit happens on
          the database side, limiting the query results.
        % offset: int ~~ None
          Specifies the offset at which the yielded items should start. Combined
          with limit this enables proper pagination.
        % order: iterable of str/2-tuple
          Defines the fields on which the output should be ordered. This should
          be a list of strings or 2-tuples. The string or first item indicates the
          field, the second argument defines descending order (desc. if True).
        % yield_unlimited_total_first: bool ~~ False
          Instead of yielding only Record objects, the first item returned is the
          number of results from the query if it had been executed without limit.
        % search: str
          Specifies what string should be searched for in the default searchable
          database columns.

        Yields:
          Record: The Record with the newest version for each versioned entry.
        """
        if not tables:
            tables = [cls.TableName()]
        if not fields:
            fields = "%s.*" % cls.TableName()
        else:
            if fields != "*":
                if type(fields) != str:
                    fields = ", ".join(connection.EscapeField(fields))
                else:
                    fields = connection.EscapeField(fields)
        if search:
            search = search.strip()
            tables, newconditions = cls._GetColumnData(tables, search)
            if conditions:
                if type(conditions) == list:
                    conditions.extend(newconditions)
                else:
                    newconditions.append(conditions)
                    conditions = newconditions
            else:
                conditions = newconditions
        field_escape = connection.EscapeField if escape else lambda x: x
        if yield_unlimited_total_first and limit is not None:
            totalcount = "SQL_CALC_FOUND_ROWS"
        else:
            totalcount = ""
        with connection as cursor:
            records = cursor.Execute(
                """
          SELECT %(totalcount)s %(fields)s
          FROM %(tables)s
          JOIN (SELECT MAX(`%(primary)s`) AS `max`
                FROM `%(table)s`
                GROUP BY `%(record_key)s`) AS `versions`
              ON (`%(table)s`.`%(primary)s` = `versions`.`max`)
          WHERE %(conditions)s
          %(order)s
          %(limit)s
          """
                % {
                    "totalcount": totalcount,
                    "primary": cls._PRIMARY_KEY,
                    "record_key": cls.RecordKey(),
                    "fields": fields,
                    "table": cls.TableName(),
                    "tables": cursor._StringTable(tables, field_escape),
                    "conditions": cursor._StringConditions(conditions, field_escape),
                    "order": cursor._StringOrder(order, field_escape),
                    "limit": cursor._StringLimit(limit, offset),
                }
            )
        if yield_unlimited_total_first and limit is not None:
            with connection as cursor:
                records.affected = cursor._Execute("SELECT FOUND_ROWS()")[0][0]
            yield records.affected
        # turn sqltalk rows into model
        records = [cls(connection, record) for record in list(records)]
        for record in records:
            yield record
        if (
            hasattr(cls, "_addToCache")
            and not fields
            or (fields == "*" and len(tables) == 1)
        ):
            list(cls._cacheListPreseed(records))

    @classmethod
    def _GetColumnData(cls, tables, search):
        """Extracts table information from the searchable columns."""
        conditions = []
        # XXX search needs to be escaped properly
        condition = 'like "%%%s%%" or ' % search
        searchcondition = ""
        for column in cls.SEARCHABLE_COLUMNS:
            columndata = column.split(".")
            if len(columndata) == 2:
                classname = columndata[0][0].upper() + columndata[0][1:]
                table = globals()[classname]
                if getattr(table, "RecordKey", None):
                    key = table.RecordKey()
                else:
                    key = table._PRIMARY_KEY
                conditions.append(
                    "`%s`.`%s` = %s.%s"
                    % (cls.TableName(), table.TableName(), table.TableName(), key)
                )
                if (
                    table.TableName() not in tables
                    and table.TableName() != cls.TableName()
                ):
                    tables.append(table.TableName())
                searchcondition += "`%s`.`%s` %s" % (
                    table.TableName(),
                    columndata[1],
                    condition,
                )
            else:
                searchcondition += "`%s`.`%s` %s" % (cls.TableName(), column, condition)
        searchcondition = "(%s)" % searchcondition[:-4]
        conditions.append(searchcondition)
        return tables, conditions


class RichModel(model.Record):
    """Provides a richer uweb Record class."""

    SEARCHABLE_COLUMNS = []

    def PagedChildren(self, classname, *args, **kwargs):
        """Return child objects with extra argument options."""
        if "conditions" in kwargs:
            kwargs["conditions"].append("%s = %d" % (self.TableName(), self.key))
        else:
            kwargs["conditions"] = "%s = %d" % (self.TableName(), self.key)
        if "offset" in kwargs and kwargs["offset"] < 0:
            kwargs["offset"] = 0
        return classname.List(*args, **kwargs)

    @classmethod
    def List(
        cls,
        connection,
        conditions=None,
        limit=None,
        offset=None,
        order=None,
        yield_unlimited_total_first=False,
        search=None,
        tables=None,
        escape=True,
        fields=None,
    ):
        """Yields a Record object for every table entry.

        Arguments:
          @ connection: object
            Database connection to use.
          % conditions: str / iterable ~~ None
            Optional query portion that will be used to limit the list of results.
            If multiple conditions are provided, they are joined on an 'AND' string.
          % limit: int ~~ None
            Specifies a maximum number of items to be yielded. The limit happens on
            the database side, limiting the query results.
          % offset: int ~~ None
            Specifies the offset at which the yielded items should start. Combined
            with limit this enables proper pagination.
          % order: iterable of str/2-tuple
            Defines the fields on which the output should be ordered. This should
            be a list of strings or 2-tuples. The string or first item indicates the
            field, the second argument defines descending order (desc. if True).
          % yield_unlimited_total_first: bool ~~ False
            Instead of yielding only Record objects, the first item returned is the
            number of results from the query if it had been executed without limit.
          % search: str
            Specifies what string should be searched for in the default searchable
            database columns.

        Yields:
          Record: Database record abstraction class.
        """
        if not tables:
            tables = [cls.TableName()]
        group = None
        if fields is None:
            fields = "%s.*" % cls.TableName()
        if search:
            search = search.strip()
            group = "%s.%s" % (
                cls.TableName(),
                (
                    cls.RecordKey()
                    if getattr(cls, "RecordKey", None)
                    else cls._PRIMARY_KEY
                ),
            )
            tables, newconditions = cls._GetColumnData(tables, search)
            if conditions:
                if type(conditions) == list:
                    conditions.extend(newconditions)
                else:
                    newconditions.append(conditions)
                    conditions = newconditions
            else:
                conditions = newconditions
        with connection as cursor:
            if hasattr(cls, "_addToCache"):
                connection.modelcache["_stats"]["queries"].append(
                    "%s VersionedRecord.List" % cls.TableName()
                )
            records = cursor.Select(
                fields=fields,
                table=tables,
                conditions=conditions,
                limit=limit,
                offset=offset,
                order=order,
                totalcount=yield_unlimited_total_first,
                escape=escape,
                group=group,
            )
        if yield_unlimited_total_first:
            yield records.affected
        records = [cls(connection, record) for record in list(records)]
        for record in records:
            yield record
        if hasattr(cls, "_addToCache"):
            # and not fields or fields == '*':
            # dont cache partial objects
            list(cls._cacheListPreseed(records))

    @classmethod
    def _GetColumnData(cls, tables, search):
        """Extracts table information from the searchable columns."""
        conditions = []
        # XXX search needs to be escaped properly
        condition = 'like "%%%s%%" or ' % search
        searchcondition = ""
        for column in cls.SEARCHABLE_COLUMNS:
            columndata = column.split(".")
            if len(columndata) == 2:
                classname = columndata[0]
                table = cls._SUBTYPES[classname]
                fkey = cls._FOREIGN_RELATIONS.get(classname, False)
                if fkey and fkey.get("LookupKey", False):
                    key = fkey.get("LookupKey")
                elif getattr(table, "RecordKey", None):
                    key = table.RecordKey()
                else:
                    key = table._PRIMARY_KEY
                conditions.append(
                    "`%s`.`%s` = %s.%s"
                    % (cls.TableName(), table.TableName(), table.TableName(), key)
                )
                if (
                    table.TableName() not in tables
                    and table.TableName() != cls.TableName()
                ):
                    tables.append(table.TableName())
                searchcondition += "`%s`.`%s` %s" % (
                    table.TableName(),
                    columndata[1],
                    condition,
                )
            else:
                searchcondition += "`%s`.`%s` %s" % (cls.TableName(), column, condition)
        if searchcondition:
            searchcondition = (
                "(%s)" % searchcondition[:-4]
            )  # TODO use ' or '.join on search conditions instead
            conditions.append(searchcondition)
        return tables, conditions
