#!/usr/bin/env python3
#
#  __init__.py
"""
Dom's tools for Tom's Obvious, Minimal Language.
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
from typing import Any, Dict, Mapping, Type, Union

# 3rd party
from domdf_python_tools.paths import PathPlus
from domdf_python_tools.typing import PathLike

# this package
from dom_toml.decoder import TomlDecoder
from dom_toml.encoder import TomlEncoder

__author__: str = "Dominic Davis-Foster"
__copyright__: str = "2021 Dominic Davis-Foster"
__license__: str = "MIT License"
__version__: str = "2.0.0"
__email__: str = "dominic@davis-foster.co.uk"

__all__ = ["dumps", "loads", "dump", "load"]


def dumps(
		data: Mapping[str, Any],
		encoder: Union[Type[TomlEncoder], TomlEncoder] = TomlEncoder,
		) -> str:
	r"""
	Convert ``data`` to a TOML string.

	:param data:
	:param encoder: The :class:`~.TomlEncoder` to use for constructing the output string.

	:returns: A string containing the ``TOML`` corresponding to ``data``.

	.. versionchanged:: 2.0.0  ``encoder`` must now be a :class:`~.TomlEncoder` type or instance.
	.. latex:clearpage::
	"""

	if isinstance(encoder, type):
		encoder = encoder()

	return ''.join(encoder.dumps(data, name=''))


def dump(
		data: Mapping[str, Any],
		filename: PathLike,
		encoder: Union[Type[TomlEncoder], TomlEncoder] = TomlEncoder,
		) -> str:
	r"""
	Writes out ``data`` as TOML to the given file.

	:param data:
	:param filename: The filename to write to.
	:param encoder: The :class:`~.TomlEncoder` to use for constructing the output string.

	:returns: A string containing the ``TOML`` corresponding to ``data``.

	.. versionchanged:: 2.0.0  ``encoder`` must now be a :class:`~.TomlEncoder` type or instance.
	"""

	filename = PathPlus(filename)
	as_toml = dumps(data, encoder=encoder)
	filename.write_clean(as_toml)
	return as_toml


def loads(
		s: str,
		decoder: Union[Type[TomlDecoder], TomlDecoder] = TomlDecoder,
		) -> Dict[str, Any]:
	r"""
	Parse the given string as TOML.

	:param s:
	:param decoder: The :class:`~.TomlEncoder` to use for constructing the output string.

	:returns: A mapping containing the ``TOML`` data.

	.. versionchanged:: 2.0.0  ``decoder`` must now be a :class:`~.TomlDecoder` type or instance.
	"""

	if not isinstance(s, str):
		raise TypeError("Expecting something like a string")

	if isinstance(decoder, type):
		decoder = decoder()

	return decoder.loads(s)


def load(
		filename: PathLike,
		decoder: Union[Type[TomlDecoder], TomlDecoder] = TomlDecoder,
		) -> Dict[str, Any]:
	r"""
	Parse TOML from the given file.

	:param filename: The filename to read from to.
	:param decoder: The :class:`~.TomlEncoder` to use for constructing the output string.

	:returns: A mapping containing the ``TOML`` data.

	.. versionchanged:: 2.0.0  ``decoder`` must now be a :class:`~.TomlDecoder` type or instance.
	"""

	return loads(
			PathPlus(filename).read_text(),
			decoder=decoder,
			)
