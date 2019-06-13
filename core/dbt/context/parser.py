import dbt.exceptions

import dbt.context.common
from dbt.adapters.factory import get_adapter


execute = False


def ref(db_wrapper, model, config, manifest):

    def ref(*args):
        if len(args) == 1 or len(args) == 2:
            model.refs.append(list(args))

        else:
            dbt.exceptions.ref_invalid_args(model, args)

        return db_wrapper.adapter.Relation.create_from_node(config, model)

    return ref


def docs(unparsed, docrefs, column_name=None):

    def do_docs(*args):
        if len(args) != 1 and len(args) != 2:
            dbt.exceptions.doc_invalid_args(unparsed, args)
        doc_package_name = ''
        doc_name = args[0]
        if len(args) == 2:
            doc_package_name = args[1]

        docref = {
            'documentation_package': doc_package_name,
            'documentation_name': doc_name,
        }
        if column_name is not None:
            docref['column_name'] = column_name

        docrefs.append(docref)

        # IDK
        return True

    return do_docs


def source(db_wrapper, model, config, manifest):
    def do_source(source_name, table_name):
        model.sources.append([source_name, table_name])
        return db_wrapper.adapter.Relation.create_from_node(config, model)

    return do_source


class Config:
    def __init__(self, model, source_config):
        self.model = model
        self.source_config = source_config

    def _transform_config(self, config):
        for oldkey in ('pre_hook', 'post_hook'):
            if oldkey in config:
                newkey = oldkey.replace('_', '-')
                if newkey in config:
                    dbt.exceptions.raise_compiler_error(
                        'Invalid config, has conflicting keys "{}" and "{}"'
                        .format(oldkey, newkey),
                        self.model
                    )
                config[newkey] = config.pop(oldkey)
        return config

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0:
            opts = args[0]
        elif len(args) == 0 and len(kwargs) > 0:
            opts = kwargs
        else:
            dbt.exceptions.raise_compiler_error(
                "Invalid inline model config",
                self.model)

        opts = self._transform_config(opts)

        self.source_config.update_in_model_config(opts)
        return ''

    def set(self, name, value):
        return self.__call__({name: value})

    def require(self, name, validator=None):
        return ''

    def get(self, name, validator=None, default=None):
        return ''


class DatabaseWrapper(dbt.context.common.BaseDatabaseWrapper):
    """The parser subclass of the database wrapper applies any explicit
    parse-time overrides.
    """
    def __getattr__(self, name):
        override = (name in self.adapter._available_ and
                    name in self.adapter._parse_replacements_)

        if override:
            return self.adapter._parse_replacements_[name]
        elif name in self.adapter._available_:
            return getattr(self.adapter, name)
        else:
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(
                    self.__class__.__name__, name
                )
            )


class Var(dbt.context.common.Var):
    def get_missing_var(self, var_name):
        # in the parser, just always return None.
        return None


def generate(model, runtime_config, manifest, source_config):
    # during parsing, we don't have a connection, but we might need one, so we
    # have to acquire it.
    # In the future, it would be nice to lazily open the connection, as in some
    # projects it would be possible to parse without connecting to the db
    with get_adapter(runtime_config).connection_named(model.get('name')):
        return dbt.context.common.generate(
            model, runtime_config, manifest, source_config, dbt.context.parser
        )


def generate_macro(model, runtime_config, manifest):
    return dbt.context.common.generate_execute_macro(
        model, runtime_config, manifest, dbt.context.parser
    )
