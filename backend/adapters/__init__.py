"""JARVIS Adapters Module - External daemon integrations"""

from .base import BaseAdapter
from .jarvis import JarvisAdapter
from .registry import AdapterRegistry, get_registry

__all__ = ['BaseAdapter', 'JarvisAdapter', 'AdapterRegistry', 'get_registry']