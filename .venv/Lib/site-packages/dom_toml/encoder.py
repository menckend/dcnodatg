#!/usr/bin/env python3
#
#  encoder.py
"""
Dom's custom encoder for Tom's Obvious, Minimal Language.

.. versionadded:: 0.2.0
"""
#
#  Copyright © 2021 Dominic Davis-Foster <dominic@davis-foster.co.uk>
#
#  Based on https://github.com/hukkin/tomli-w
#  MIT Licensed
#  Copyright (c) 2021 Taneli Hukkinen
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
import pathlib
import string
from datetime import date, datetime, time
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Dict, Iterator, List, Mapping, Tuple, Union

# this package
from dom_toml.decoder import InlineTableDict

__all__ = ["TomlEncoder", "TomlArraySeparatorEncoder", "TomlNumpyEncoder", "TomlPathlibEncoder"]

ASCII_CTRL = frozenset(chr(i) for i in range(32)) | frozenset(chr(127))
ILLEGAL_BASIC_STR_CHARS = frozenset('"\\') | ASCII_CTRL - frozenset('\t')
BARE_KEY_CHARS = frozenset(string.ascii_letters + string.digits + "-_")
ARRAY_TYPES = (list, tuple)
ARRAY_INDENT = ' ' * 4

COMPACT_ESCAPES = MappingProxyType({
		'\x08': "\\b",  # backspace
		'\n': "\\n",  # linefeed
		'\x0c': "\\f",  # form feed
		'\r': "\\r",  # carriage return
		'"': '\\"',  # quote
		'\\': "\\\\",  # backslash
		})


class TomlEncoder:
	"""
	TOML encoder which wraps long lists onto multiple lines and adds a blank line before arrays of tables.

	:param preserve:
	:param allow_multiline:
	:param separator:

	.. versionchanged:: 0.2.0  Moved from ``__init__.py``
	.. versionchanged:: 2.0.0  Added ``allow_multiline``  argument.
	.. autosummary-widths:: 45/100
	"""

	# The maximum width of the list **value**, after which it will be wrapped.
	max_width: int = 100

	allow_multiline: bool

	# cache rendered inline tables (mapping from object id to rendered inline table)
	inline_table_cache: Dict[int, str]

	def __init__(self, preserve: bool = True, multiline_strings: bool = False):
		self.preserve = preserve
		self.allow_multiline = multiline_strings
		self.inline_table_cache = {}

	def dumps(
			self,
			table: Mapping[str, Any],
			*,
			name: str,
			inside_aot: bool = False,
			) -> Iterator[str]:
		"""
		Serialise the given table.

		:param name: The table name.
		:param inside_aot:

		:rtype:

		.. versionadded:: 2.0.0
		"""

		yielded = False
		literals = []
		tables: List[Tuple[str, Any, bool]] = []  # => [(key, value, inside_aot)]
		for k, v in table.items():
			if v is None:
				continue
			elif self.preserve and isinstance(v, InlineTableDict):
				literals.append((k, v))
			elif isinstance(v, dict):
				tables.append((k, v, False))
			elif self._is_aot(v) and not all(self._is_suitable_inline_table(t) for t in v):
				tables.extend((k, t, True) for t in v)
			else:
				literals.append((k, v))

		if inside_aot or name and (literals or not tables):
			yielded = True
			yield f"[[{name}]]\n" if inside_aot else f"[{name}]\n"

		if literals:
			yielded = True
			for k, v in literals:
				yield f"{self.format_key_part(k)} = {self.format_literal(v)}\n"

		for k, v, in_aot in tables:
			if yielded:
				yield '\n'
			else:
				yielded = True

			key_part = self.format_key_part(k)
			display_name = f"{name}.{key_part}" if name else key_part

			yield from self.dumps(v, name=display_name, inside_aot=in_aot)

	def format_literal(self, obj: object, *, nest_level: int = 0) -> str:
		"""
		Format a literal value.

		:param obj:
		:param nest_level:

		:rtype:

		.. versionadded:: 2.0.0
		"""

		if isinstance(obj, bool):
			return "true" if obj else "false"
		if isinstance(obj, (int, float, date, datetime)):
			return str(obj)
		if isinstance(obj, Decimal):
			return self.format_decimal(obj)
		if isinstance(obj, time):
			if obj.tzinfo:
				raise ValueError("TOML does not support offset times")
			return str(obj)
		if isinstance(obj, str):
			return self.format_string(obj, allow_multiline=self.allow_multiline)
		if isinstance(obj, ARRAY_TYPES):
			return self.format_inline_array(obj, nest_level)
		if isinstance(obj, dict):
			return self.format_inline_table(obj)
		raise TypeError(f"Object of type {type(obj)} is not TOML serializable")

	def format_decimal(self, obj: Decimal) -> str:
		"""
		Format a decimal value.

		:param obj:

		:rtype:

		.. versionadded:: 2.0.0
		"""

		if obj.is_nan():
			return "nan"
		if obj == Decimal("inf"):
			return "inf"
		if obj == Decimal("-inf"):
			return "-inf"
		return str(obj)

	def format_inline_table(self, obj: dict) -> str:
		"""
		Format an inline table.

		:param obj:

		:rtype:

		.. versionadded:: 2.0.0
		"""

		# check cache first
		obj_id = id(obj)
		if obj_id in self.inline_table_cache:
			return self.inline_table_cache[obj_id]

		if not obj:
			rendered = "{}"
		else:
			rendered = (
					"{ "
					+ ", ".join(f"{self.format_key_part(k)} = {self.format_literal(v)}" for k, v in obj.items())
					+ " }"
					)
		self.inline_table_cache[obj_id] = rendered
		return rendered

	def format_inline_array(self, obj: Union[Tuple, List], nest_level: int) -> str:
		"""
		Format an inline array.

		:param obj:
		:param nest_level:

		:rtype:

		.. versionadded:: 2.0.0
		"""

		if not len(obj):
			return "[]"

		item_indent = ARRAY_INDENT * (1 + nest_level)
		closing_bracket_indent = ARRAY_INDENT * nest_level
		single_line = "[ " + ", ".join(
				self.format_literal(item, nest_level=nest_level + 1) for item in obj
				) + f",]"

		if len(single_line) <= self.max_width:
			return single_line
		else:
			start = "[\n"
			body = ",\n".join(item_indent + self.format_literal(item, nest_level=nest_level + 1) for item in obj)
			end = f",\n{closing_bracket_indent}]"
			return start + body + end

	def format_key_part(self, part: str) -> str:
		"""
		Format part of a key.

		:param part:

		:rtype:

		.. versionadded:: 2.0.0
		"""

		if part and BARE_KEY_CHARS.issuperset(part):
			return part
		return self.format_string(part, allow_multiline=False)

	def format_string(self, s: str, *, allow_multiline: bool) -> str:
		"""
		Format a string.

		:param s:
		:param allow_multiline:

		:rtype:

		.. versionadded:: 2.0.0
		.. latex:clearpage::
		"""

		do_multiline = allow_multiline and '\n' in s
		if do_multiline:
			result = '"""\n'
			s = s.replace("\r\n", '\n')
		else:
			result = '"'

		pos = seq_start = 0
		while True:
			try:
				char = s[pos]
			except IndexError:
				result += s[seq_start:pos]
				if do_multiline:
					return result + '"""'
				return result + '"'
			if char in ILLEGAL_BASIC_STR_CHARS:
				result += s[seq_start:pos]
				if char in COMPACT_ESCAPES:
					if do_multiline and char == '\n':
						result += '\n'
					else:
						result += COMPACT_ESCAPES[char]
				else:
					result += "\\u" + hex(ord(char))[2:].rjust(4, '0')
				seq_start = pos + 1
			pos += 1

	def _is_aot(self, obj: Any) -> bool:
		"""
		Decides if an object behaves as an array of tables (i.e. a nonempty list of dicts).

		:param obj:
		"""

		return bool(isinstance(obj, ARRAY_TYPES) and obj and all(isinstance(v, dict) for v in obj))

	def _is_suitable_inline_table(self, obj: dict) -> bool:
		"""
		Use heuristics to decide if the inline-style representation is a good choice for a given table.

		:param obj:
		"""

		# if self.preserve and isinstance(dict, InlineTableDict):
		# 	return True

		rendered_inline = f"{ARRAY_INDENT}{self.format_inline_table(obj)},"
		return len(rendered_inline) <= self.max_width and '\n' not in rendered_inline


class TomlPathlibEncoder(TomlEncoder):
	"""
	TOML Encoder with pathlib support.

	.. versionadded:: 2.0.0
	"""

	def format_literal(self, obj: object, *, nest_level: int = 0) -> str:
		"""
		Format a literal value.

		:param obj:
		:param nest_level:
		"""

		if isinstance(obj, pathlib.PurePath):
			obj = str(obj)
		return super().format_literal(obj, nest_level=nest_level)


class TomlNumpyEncoder(TomlEncoder):
	"""
	TOML Encoder with support for numpy types.

	.. versionadded:: 2.0.0
	"""

	def format_literal(self, obj: object, *, nest_level: int = 0) -> str:
		"""
		Format a literal value.

		:param obj:
		:param nest_level:
		"""

		# 3rd party
		import numpy as np  # nodep

		if isinstance(obj, (np.float16, np.float32, np.float64)):
			return self._dump_float(obj)  # type: ignore[arg-type]

		elif isinstance(obj, (np.int16, np.int32, np.int64)):
			return self._dump_int(obj)  # type: ignore[arg-type]

		elif isinstance(obj, np.ndarray):
			return self.format_inline_array(obj, nest_level)  # type: ignore[arg-type]

		return super().format_literal(obj, nest_level=nest_level)

	def _dump_int(self, v: int) -> str:
		return f"{int(v)}"

	def _dump_float(self, v: float) -> str:
		return f"{v}".replace("e+0", "e+").replace("e-0", "e-")


class TomlArraySeparatorEncoder(TomlEncoder):
	"""
	TOML Encoder with adjustable array separator.

	:param preserve:
	:param allow_multiline:
	:param separator:

	.. versionadded:: 2.0.0
	"""

	def __init__(self, preserve: bool = True, multiline_strings: bool = False, separator: str = ','):
		self.preserve = preserve
		self.allow_multiline = multiline_strings
		self.inline_table_cache = {}

		if not separator.strip():
			separator = ',' + separator
		elif separator.strip(' \t\n\r,'):
			raise ValueError("Invalid separator for arrays")

		self.separator = separator

	def format_inline_array(self, obj: Union[Tuple, List], nest_level: int) -> str:
		"""
		Format an inline array.

		:param obj:
		:param nest_level:
		"""

		t = []
		retval = '['
		for u in obj:
			t.append(self.format_literal(u, nest_level=nest_level))
		while t != []:
			s: List[str] = []
			for u in t:
				if isinstance(u, list):
					s.extend(r for r in u)
				else:
					retval += ' ' + str(u) + self.separator
			t = s
		retval += ']'
		return retval
