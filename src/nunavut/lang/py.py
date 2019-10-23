#
# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Copyright (C) 2018-2019  UAVCAN Development Team  <uavcan.org>
# This software is distributed under the terms of the MIT License.
#
"""
    Filters for generating python. All filters in this
    module will be available in the template's global namespace as ``py``.
"""
import typing
import keyword
import builtins
import pydsdl

from .. import SupportsTemplateEnv, templateEnvironmentFilter
from .c import VariableNameEncoder


@templateEnvironmentFilter
def filter_to_template_unique_name(env: SupportsTemplateEnv, base_token: str) -> str:
    """
    Filter that takes a base token and forms a name that is very
    likely to be unique within the template the filter is invoked. This
    name is also very likely to be a valid Python identifier.

    .. IMPORTANT::

        The exact tokens generated may change between major or minor versions
        of this library. The only guarantee provided is that the tokens
        will be stable for the same version of this library given the same
        input.

        Also note that name uniqueness is only likely within a given template.
        Between templates there is no guarantee of uniqueness and,
        since this library does not lex generated source, there is no guarantee
        that the generated name does not conflict with a name generated by
        another means.

    Example::

        {{ "foo" | py.to_template_unique_name }}
        {{ "foo" | py.to_template_unique_name }}
        {{ "bar" | py.to_template_unique_name }}
        {{ "i like coffee" | py.to_template_unique_name }}

    Results Example::

        # These are the likely results but the specific token
        # generated is not strongly specified.
        _foo0_
        _foo1_
        _bar0_
        _i like coffee0_ # Note that this is not a valid python identifier.
                         # This filter does _not_ lex the base_token argument.


    :param str base_token: A token to include in the base name.
    :returns: A name that is likely to be valid python identifier and is likely to
        be unique within the file generated by the current template.
    """
    return env.globals['_unique_name_generator']('py', base_token, '_', '_')  # type: ignore


PYTHON_RESERVED_IDENTIFIERS = frozenset(map(str, list(keyword.kwlist) + dir(builtins)))  # type: typing.FrozenSet[str]


def filter_id(instance: typing.Any, stropping_suffix: str = '_', encoding_prefix: str = 'ZX') -> str:
    """
    Filter that produces a valid Python identifier for a given object. The encoding may not
    be reversable.

    .. invisible-code-block: python

        from nunavut.lang.py import filter_id

    .. code-block:: python

        # Given
        I = 'I like python'

        # and
        template = '{{ I | id }}'

        # then
        rendered = 'I_like_python'


    .. invisible-code-block: python

        jinja_filter_tester(filter_id, template, rendered, I=I)

    .. code-block:: python

        # Given
        I = '&because'

        # and
        template = '{{ I | id }}'

        # then
        rendered = 'ZX0026because'


    .. invisible-code-block: python

        jinja_filter_tester(filter_id, template, rendered, I=I)


    .. code-block:: python

        # Given
        I = 'if'

        # and
        template = '{{ I | id }}'

        # then
        rendered = 'if_'


    .. invisible-code-block: python

        jinja_filter_tester(filter_id, template, rendered, I=I)


    .. code-block:: python

        # Given
        I = 'if'

        # and
        template = '{{ I | id("stropped_") }}'

        # then
        rendered = 'ifstropped_'


    .. invisible-code-block: python

        jinja_filter_tester(filter_id, template, rendered, I=I)


    :param any instance:        Any object or data that either has a name property or can be converted
                                to a string.
    :param str stropping_suffix: String appended to the resolved instance name if the encoded value
                                is a reserved keyword in python.
    :param str encoding_prefix: The string to insert before any four digit unicode number used to represent
                                an illegal character.
                                Note that the caller must ensure the prefix itself consists of only valid
                                characters for Python identifiers.
    :returns: A token that is a valid Python identifier, is not a reserved keyword, and is transformed
              in a deterministic manner based on the provided instance.
    """
    if hasattr(instance, 'name'):
        raw_name = str(instance.name)  # type: str
    else:
        raw_name = str(instance)

    # We use the C variable name encoder since the variable token rules are
    # compatible.
    return VariableNameEncoder('', stropping_suffix, encoding_prefix, False).strop(raw_name,
                                                                                   PYTHON_RESERVED_IDENTIFIERS)


def filter_full_reference_name(t: pydsdl.CompositeType) -> str:
    return '{full}_{major}_{minor}'.format(full=t.full_name, major=t.version.major, minor=t.version.minor)


def filter_short_reference_name(t: pydsdl.CompositeType) -> str:
    return '{short}_{major}_{minor}'.format(short=t.short_name, major=t.version.major, minor=t.version.minor)


def filter_alignment_prefix(offset: pydsdl.BitLengthSet) -> str:
    if isinstance(offset, pydsdl.BitLengthSet):
        return 'aligned' if offset.is_aligned_at_byte() else 'unaligned'
    else:  # pragma: no cover
        raise TypeError('Expected BitLengthSet, got {}'.format(type(offset).__name__))


def filter_imports(t: pydsdl.CompositeType) -> typing.List[str]:
    # Make a list of all attributes defined by this type
    if isinstance(t, pydsdl.ServiceType):
        atr = t.request_type.attributes + t.response_type.attributes
    else:
        atr = t.attributes

    # Extract data types of said attributes; for type constructors such as arrays extract the element type
    dep_types = list(map(lambda x: x.data_type, atr))  # type: ignore
    for t in dep_types[:]:
        if isinstance(t, pydsdl.ArrayType):
            dep_types.append(t.element_type)

    # Make a list of unique full namespaces of referenced composites
    return list(sorted(set(x.full_namespace for x in dep_types if isinstance(x, pydsdl.CompositeType))))


def filter_longest_id_length(attributes: typing.List[pydsdl.Attribute]) -> int:
    return max(map(len, map(filter_id, attributes)))


def filter_bit_length_set(values: typing.Optional[typing.Union[typing.Iterable[int], int]]) -> pydsdl.BitLengthSet:
    return pydsdl.BitLengthSet(values)
