#!/usr/bin/env python3
#
#  decoder.py
"""
TOML decoders.

.. versionadded:: 0.2.0
"""
#
#  Copyright © 2021 Dominic Davis-Foster <dominic@davis-foster.co.uk>
#
#  Based on https://github.com/uiri/toml
#  MIT Licensed
#  Copyright 2013-2019 William Pearson
#  Copyright 2015-2016 Julien Enselme
#  Copyright 2016 Google Inc.
#  Copyright 2017 Samuel Vasko
#  Copyright 2017 Nate Prewitt
#  Copyright 2017 Jack Evans
#  Copyright 2019 Filippo Broggini
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
from typing import Any, Callable, Dict, Tuple

# 3rd party
import tomli

__all__ = ["InlineTableDict", "TomlDecoder", "TomlPureDecoder"]


class InlineTableDict(dict):
	"""
	Subclass of dict for inline tables.

	.. versionadded:: 2.0.0
	"""


class TomlDecoder:
	"""
	TOML decoder which uses a dict-subclass for inline tables.

	.. versionadded:: 2.0.0
	"""

	def loads(self, s: str) -> Dict[str, Any]:
		"""
		Parse the given string as TOML.

		:param s:

		:returns: A mapping containing the ``TOML`` data.

		.. latex:clearpage::
		"""

		try:
			pit = tomli._parser.parse_inline_table

			def _parse_inline_table(src: str, pos: int, parse_float: Callable[[str], Any]) -> Tuple[int, Dict]:
				pos, table = pit(src, pos, parse_float)
				return pos, InlineTableDict(table)

			tomli._parser.parse_inline_table = _parse_inline_table
			return tomli.loads(s)
		finally:
			tomli._parser.parse_inline_table = pit


class TomlPureDecoder(TomlDecoder):
	"""
	TOML decoder which uses pure-Python dictionaries for inline tables.
	"""

	def loads(self, s: str) -> Dict[str, Any]:
		"""
		Parse the given string as TOML.

		:param s:

		:returns: A mapping containing the ``TOML`` data.

		.. versionadded:: 2.0.0
		"""

		return tomli.loads(s)
