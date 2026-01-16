"""
Plugin registry system
Ported from plugins.mjs
"""

from .util.helpers import throw_error


class PluginRegistry:
    """Registry for file parsers, segment parsers, and file readers"""

    def __init__(self):
        self._plugins = {}

    def register(self, key, plugin_class):
        """Register a plugin"""
        self._plugins[key] = plugin_class

    def has(self, key):
        """Check if plugin is registered"""
        return key in self._plugins

    def get(self, key, options=None):
        """Get a plugin class"""
        if key not in self._plugins:
            return None
        return self._plugins[key]

    def __setitem__(self, key, value):
        """Support dict-like assignment: registry[key] = value"""
        self._plugins[key] = value

    def __getitem__(self, key):
        """Support dict-like access: registry[key]"""
        return self._plugins[key]

    def __contains__(self, key):
        """Support 'in' operator: key in registry"""
        return key in self._plugins

    def __iter__(self):
        """Iterate over plugins"""
        return iter(self._plugins.items())

    def items(self):
        """Get all plugin items"""
        return self._plugins.items()


# Global plugin registries
file_parsers = PluginRegistry()
segment_parsers = PluginRegistry()
file_readers = PluginRegistry()


def throw_not_loaded(type_name, key):
    """Throw error for missing plugin"""
    throw_error(f"{type_name} '{key}' is not loaded")
