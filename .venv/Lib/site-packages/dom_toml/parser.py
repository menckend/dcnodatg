#!/usr/bin/env python3
#
#  parser.py
"""
Abstract base class for TOML configuration parsers.

.. versionadded:: 0.2.0
"""
#
#  Copyright © 2021 Dominic Davis-Foster <dominic@davis-foster.co.uk>
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#  DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
#  OR OTHER DEALINGS IN THE SOFTWARE.
#

# stdlib
from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, Dict, Iterable, List, Optional, Tuple, Type, TypeVar, Union

# this package
import dom_toml

__all__ = ["AbstractConfigParser", "BadConfigError", "construct_path", "TOML_TYPES"]

TOML_TYPES = Any


class BadConfigError(ValueError):
	"""
	Indicates an error in the TOML configuration.

	:param documentation: A link to the documentation that explains the problematic option.
		This is not used by the class itself, except setting it as the ``documentation`` attribute,
		The intention is for code catching this exception to display this URL to the user.

	.. versionchanged:: 0.6.0  Added the ``documentation`` keyword argument and attribute.
	"""

	#: A link to the documentation that explains the problematic option.
	documentation: Optional[str]

	def __init__(self, *args, documentation: Optional[str] = None) -> None:
		super().__init__(*args)
		self.documentation = documentation


def construct_path(path: Iterable[str]) -> str:
	"""
	Construct a dotted path to a key.

	:param path: The path elements.
	"""

	return '.'.join([dom_toml.dumps({elem: 0})[:-5] for elem in path])


_C = TypeVar("_C", bound=Callable)


class AbstractConfigParser(ABC):
	"""
	Abstract base class for TOML configuration parsers.

	.. autoclasssumm:: AbstractConfigParser
	.. latex:clearpage::
	"""

	defaults: ClassVar[Dict[str, Any]]
	"""
	A mapping of key names to default values.

	.. versionadded:: 0.3.0
	"""

	factories: ClassVar[Dict[str, Callable[..., Any]]]
	"""
	A mapping of key names to default value factories.

	.. versionadded:: 0.3.0

	.. note:: If both a default and a factory are defined for a key the factory takes precedence.

	.. note::

		``defaults`` and ``factories`` are reset for each subclass.
		To disable this behaviour set the ``inherit_defaults`` keyword argument on the class:

		.. code-block:: python

			class MyParser(AbstractConfigParser, inherit_default=True):
				pass
	"""

	def __init_subclass__(cls, **kwargs) -> None:
		if not kwargs.get("inherit_defaults", False):
			if "defaults" not in cls.__dict__:
				cls.defaults = {}

			if "factories" not in cls.__dict__:
				cls.factories = {}

	@staticmethod
	def assert_type(
			obj: Any,
			expected_type: Union[Type, Tuple[Type, ...]],
			path: Iterable[str],
			what: str = "type",
			) -> None:
		"""
		Assert that ``obj`` is of type ``expected_type``, otherwise raise an error with a helpful message.

		:param obj: The object to check the type of.
		:param expected_type: The expected type.
		:param path: The elements of the path to ``obj`` in the TOML mapping.
		:param what: What ``obj`` is, e.g. ``'type'``, ``'value type'``.

		.. seealso:: :meth:`~.assert_value_type` and :meth:`~.assert_indexed_type`
		"""

		if not isinstance(obj, expected_type):
			name = construct_path(path)
			raise TypeError(f"Invalid {what} for {name!r}: expected {expected_type!r}, got {type(obj)!r}")

	@staticmethod
	def assert_indexed_type(
			obj: Any,
			expected_type: Union[Type, Tuple[Type, ...]],
			path: Iterable[str],
			idx: int = 0,
			) -> None:
		"""
		Assert that ``obj`` is of type ``expected_type``, otherwise raise an error with a helpful message.

		:param obj: The object to check the type of.
		:param expected_type: The expected type.
		:param path: The elements of the path to ``obj`` in the TOML mapping.
		:param idx: The index of ``obj`` in the array.

		.. seealso:: :meth:`~.assert_type`, and :meth:`~.assert_value_type`
		"""

		if not isinstance(obj, expected_type):
			name = construct_path(path) + f"[{idx}]"
			raise TypeError(f"Invalid type for {name!r}: expected {expected_type!r}, got {type(obj)!r}")

	def assert_value_type(
			self,
			obj: Any,
			expected_type: Union[Type, Tuple[Type, ...]],
			path: Iterable[str],
			) -> None:
		"""
		Assert that the value ``obj`` is of type ``expected_type``, otherwise raise an error with a helpful message.

		:param obj: The object to check the type of.
		:param expected_type: The expected type.
		:param path: The elements of the path to ``obj`` in the TOML mapping.

		.. seealso:: :meth:`~.assert_type` and :meth:`~.assert_indexed_type`
		"""

		self.assert_type(obj, expected_type, path, "value type")

	@property
	@abstractmethod
	def keys(self) -> List[str]:  # pragma: no cover
		"""
		The keys to parse from the TOML file.
		"""

		raise NotImplementedError

	def parse(
			self,
			config: Dict[str, TOML_TYPES],
			set_defaults: bool = False,
			) -> Dict[str, TOML_TYPES]:
		r"""
		Parse the TOML configuration.

		This function iterates over the list of keys given in :attr:`~.keys`.
		For each key, it searches for a method on the class called :file:`parse_{<key>}`.

		* If the method exists, that method is called, passing the value as the only argument.
		  The value returned from that method is included in the parsed configuration.
		  The signature of those methods is:

		  .. parsed-literal::

			def visit_<key>(
				self,
				config: :class:`typing.Dict`\[:class:`str`\, :py:obj:`typing.Any`\],
				) -> :py:obj:`typing.Any`\:

		* If the method doesn't exist, the value is included in the parsed configuration unchanged.

		* Missing keys are ignored. Override this function in a subclass if you need that behaviour.

		Once all keys have been parsed the configuration is returned.

		:param config:
		:param set_defaults: If :py:obj:`True`, the values in :attr:`.AbstractConfigParser.defaults`
			and :attr:`.AbstractConfigParser.factories` will be set as defaults for the returned mapping.

		.. versionchanged:: 0.3.0

			Added the ``set_defaults`` keyword argument.
		"""

		parsed_config = {}

		for key in self.keys:
			if key not in config:
				# Ignore absent values
				pass

			elif hasattr(self, f"parse_{key.replace('-', '_')}"):
				parsed_config[key] = getattr(self, f"parse_{key.replace('-', '_')}")(config)

			elif key in config:
				parsed_config[key] = config[key]

		if set_defaults:
			for key, value in self.defaults.items():
				parsed_config.setdefault(key, value)

			for key, factory in self.factories.items():
				value = factory()
				parsed_config.setdefault(key, value)

		return parsed_config
