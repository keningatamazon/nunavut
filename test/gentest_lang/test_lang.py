#
# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Copyright (C) 2018-2019  UAVCAN Development Team  <uavcan.org>
# This software is distributed under the terms of the MIT License.
#

import inspect
from pathlib import Path
from typing import Dict

import pytest
from pydsdl import read_namespace

from nunavut import build_namespace_tree
from nunavut.jinja import Generator
from nunavut.lang import Language, LanguageContext
from nunavut.lang.c import filter_id as c_filter_id
from nunavut.lang.cpp import filter_id as cpp_filter_id
from nunavut.lang.py import filter_id as py_filter_id


class Dummy:

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

# +---------------------------------------------------------------------------+
# | PARAMETERIZED TESTS
# +---------------------------------------------------------------------------+


def ptest_lang_c(gen_paths, implicit, unique_name_evaluator):  # type: ignore
    """ Generates and verifies JSON with values filtered using the c language support module.
    """

    root_namespace_dir = gen_paths.dsdl_dir / Path("langtest")
    if implicit:
        templates_dirs = [gen_paths.templates_dir / Path("implicit") / Path("c")]
    else:
        templates_dirs = [gen_paths.templates_dir / Path("explicit")]

    templates_dirs.append(gen_paths.templates_dir / Path("common"))

    root_namespace = str(root_namespace_dir)
    compound_types = read_namespace(root_namespace, '', allow_unregulated_fixed_port_id=True)
    language_context = LanguageContext('c' if implicit else None, '.h' if not implicit else None)
    namespace = build_namespace_tree(compound_types,
                                     root_namespace_dir,
                                     gen_paths.out_dir,
                                     language_context)
    generator = Generator(namespace,
                          False,
                          language_context,
                          templates_dirs)
    generator.generate_all(False)

    # Now read back in and verify
    outfile = gen_paths.find_outfile_in_namespace("langtest.c.TestType", namespace)

    assert (outfile is not None)

    generated_values = {}  # type: Dict
    with open(str(outfile), 'r') as python_file:
        exec(python_file.read(), generated_values)

    assert len(generated_values) > 0

    lang_c_output = generated_values["tests"]["lang_c"]
    assert lang_c_output["namespace"] == "langtest.c"
    assert lang_c_output["namespace_macrofy"] == "LANGTEST_C"

    assert lang_c_output["ctype_std truncated uint8"] == "uint8_t"
    assert lang_c_output["ctype_std saturated int8"] == "int8_t"
    assert lang_c_output["ctype_std truncated uint9"] == "uint16_t"
    assert lang_c_output["ctype_std saturated int9"] == "int16_t"

    assert lang_c_output["ctype truncated uint8"] == "unsigned char"
    assert lang_c_output["ctype saturated int8"] == "char"
    assert lang_c_output["ctype truncated uint9"] == "unsigned int"
    assert lang_c_output["ctype saturated int9"] == "int"

    assert lang_c_output["ctype_std truncated uint32"] == "uint32_t"
    assert lang_c_output["ctype_std saturated int32"] == "int32_t"
    assert lang_c_output["ctype_std truncated uint64"] == "uint64_t"
    assert lang_c_output["ctype_std saturated int64"] == "int64_t"

    assert lang_c_output["ctype truncated uint32"] == "unsigned long"
    assert lang_c_output["ctype saturated int32"] == "long"
    assert lang_c_output["ctype truncated uint64"] == "unsigned long long"
    assert lang_c_output["ctype saturated int64"] == "long long"

    assert lang_c_output["ctype saturated bool"] == "BOOL"
    assert lang_c_output["ctype_std saturated bool"] == "bool"

    unique_name_evaluator(r'_nAME\d+_', lang_c_output["unique_name_0"])
    unique_name_evaluator(r'_nAME\d+_', lang_c_output["unique_name_1"])
    unique_name_evaluator(r'_naME\d+_', lang_c_output["unique_name_2"])
    unique_name_evaluator(r'_\d+_', lang_c_output["unique_name_3"])

    return generated_values


def ptest_lang_cpp(gen_paths, implicit):  # type: ignore
    """Generates and verifies JSON with values filtered using the cpp language module.
    """

    root_namespace_dir = gen_paths.dsdl_dir / Path("langtest")
    root_namespace = str(root_namespace_dir)
    compound_types = read_namespace(root_namespace, '', allow_unregulated_fixed_port_id=True)
    if implicit:
        templates_dirs = [gen_paths.templates_dir / Path("implicit") / Path("cpp")]
    else:
        templates_dirs = [gen_paths.templates_dir / Path("explicit")]

    templates_dirs.append(gen_paths.templates_dir / Path("common"))

    language_context = LanguageContext('cpp' if implicit else None, '.hpp' if not implicit else None)

    namespace = build_namespace_tree(compound_types,
                                     root_namespace_dir,
                                     gen_paths.out_dir,
                                     language_context)

    generator = Generator(namespace,
                          False,
                          language_context,
                          templates_dirs)

    generator.generate_all(False)

    # Now read back in and verify
    outfile = gen_paths.find_outfile_in_namespace("langtest.cpp.ns.TestType", namespace)

    assert (outfile is not None)

    generated_values = {}  # type: Dict
    with open(str(outfile), 'r') as python_file:
        exec(python_file.read(), generated_values)

    assert len(generated_values)

    lang_cpp_output = generated_values["tests"]["lang_cpp"]
    assert lang_cpp_output["namespace"] == "langtest.cpp.ns"
    assert lang_cpp_output["namespace_open"] == r'''namespace langtest
{
namespace cpp
{
namespace ns
{
'''
    assert lang_cpp_output["namespace_open_wo_nl"] == r'''namespace langtest {
namespace cpp {
namespace ns {
'''
    assert lang_cpp_output["namespace_close"] == r'''}
}
}
'''
    assert lang_cpp_output["namespace_close_w_comments"] == r'''} // namespace ns
} // namespace cpp
} // namespace langtest
'''
    return generated_values


def ptest_lang_py(gen_paths, implicit, unique_name_evaluator):  # type: ignore
    """ Generates and verifies JSON with values filtered using the python language support module.
    """

    root_namespace_dir = gen_paths.dsdl_dir / Path("langtest")
    root_namespace = str(root_namespace_dir)
    if implicit:
        templates_dirs = [gen_paths.templates_dir / Path("implicit") / Path("py")]
    else:
        templates_dirs = [gen_paths.templates_dir / Path("explicit")]

    templates_dirs.append(gen_paths.templates_dir / Path("common"))

    compound_types = read_namespace(root_namespace, '', allow_unregulated_fixed_port_id=True)

    language_context = LanguageContext('py' if implicit else None, '.py' if not implicit else None)

    namespace = build_namespace_tree(compound_types,
                                     root_namespace_dir,
                                     gen_paths.out_dir,
                                     language_context)
    generator = Generator(namespace,
                          False,
                          language_context,
                          templates_dirs)

    generator.generate_all(False)

    # Now read back in and verify
    outfile = gen_paths.find_outfile_in_namespace("langtest.py.TestType", namespace)

    assert (outfile is not None)

    generated_values = {}  # type: Dict
    with open(str(outfile), 'r') as python_file:
        exec(python_file.read(), generated_values)

    assert len(generated_values) > 0

    lang_py_output = generated_values["tests"]["lang_py"]
    unique_name_evaluator(r'_NAME\d+_', lang_py_output["unique_name_0"])
    unique_name_evaluator(r'_NAME\d+_', lang_py_output["unique_name_1"])
    unique_name_evaluator(r'_name\d+_', lang_py_output["unique_name_2"])
    assert "identifier_zero" == lang_py_output["id_0"]

    many_unique_names = lang_py_output.get("many_unique_names")
    if many_unique_names is not None:
        for name in many_unique_names:
            unique_name_evaluator(r'_f\d+_', name)

    return generated_values

# +---------------------------------------------------------------------------+
# | TESTS
# +---------------------------------------------------------------------------+


def test_lang_c(gen_paths, unique_name_evaluator):  # type: ignore
    """ Generates and verifies JSON with values filtered using the c language support module.
    """
    generated_values = ptest_lang_c(gen_paths, True, unique_name_evaluator)
    lang_any = generated_values["tests"]["lang_any"]
    assert lang_any['id_0'] == '_123_class__for_u2___ZX0028ZX002Aother_stuffZX002DZX0026ZX002DsuchZX0029'
    assert lang_any['id_1'] == '_reserved'
    assert lang_any['id_2'] == '_ZX005Falso_reserved'
    assert lang_any['id_3'] == '_register'
    assert lang_any['id_4'] == 'False'
    assert lang_any['id_5'] == '_return'
    assert lang_any['id_6'] == ':poop:return'
    assert lang_any['id_7'] == 'I_ZX2764_UAVCAN'
    assert lang_any['id_8'] == 'I_0x2764_UAVCAN'

    assert lang_any['id_9'] == 'str'
    assert lang_any['id_A'] == '_strr'
    assert lang_any['id_B'] == '_uINT_FOO_MIN'
    assert lang_any['id_C'] == '_iNT_C'
    assert lang_any['id_D'] == '_lC_Is_reserved'
    assert lang_any['id_E'] == 'NOT_ATOMIC_YO'
    assert lang_any['id_F'] == '_aTOMIC_YO'

    assert '_flight__time' == c_filter_id(Dummy('_Flight__time'))


def test_lang_c_explicit(gen_paths, unique_name_evaluator):  # type: ignore
    """
    Generates and verifies JSON with values filtered using the c language support module using
    explicit language feature names.
    """
    ptest_lang_c(gen_paths, False, unique_name_evaluator)


def test_lang_cpp(gen_paths):  # type: ignore
    """
    Generates and verifies JSON with values filtered using the cpp language module.
    """

    generated_values = ptest_lang_cpp(gen_paths, True)
    lang_any = generated_values["tests"]["lang_any"]
    assert lang_any['id_0'] == '_123_class_ZX005Ffor_u2_ZX005F_ZX0028ZX002Aother_stuffZX002DZX0026ZX002DsuchZX0029'
    assert lang_any['id_1'] == '_reserved'
    assert lang_any['id_2'] == '_ZX005Falso_reserved'
    assert lang_any['id_3'] == '_register'
    assert lang_any['id_4'] == 'False'
    assert lang_any['id_5'] == '_return'
    assert lang_any['id_6'] == ':poop:return'
    assert lang_any['id_7'] == 'I_ZX2764_UAVCAN'
    assert lang_any['id_8'] == 'I_0x2764_UAVCAN'
    assert lang_any['id_9'] == 'str'
    assert lang_any['id_A'] == '_strr'
    assert lang_any['id_B'] == '_uINT_FOO_MIN'
    assert lang_any['id_C'] == '_iNT_C'
    assert lang_any['id_D'] == '_lC_Is_reserved'
    assert lang_any['id_E'] == 'NOT_ATOMIC_YO'
    assert lang_any['id_F'] == '_aTOMIC_YO'

    with pytest.raises(RuntimeError):
        cpp_filter_id('foo', '_', '__')

    assert '_flight_ZX005Ftime' == cpp_filter_id(Dummy('_Flight__time'))


def test_lang_cpp_explicit(gen_paths):  # type: ignore
    """
    Generates and verifies JSON with values filtered using the cpp language module using
    explicit language feature names.
    """

    ptest_lang_cpp(gen_paths, False)


def test_lang_py_implicit(gen_paths, unique_name_evaluator):  # type: ignore
    """ Generates and verifies JSON with values filtered using the python language support module.
    """

    generated_values = ptest_lang_py(gen_paths, True, unique_name_evaluator)
    lang_any = generated_values["tests"]["lang_any"]
    assert lang_any['id_0'] == '_123_class__for_u2___ZX0028ZX002Aother_stuffZX002DZX0026ZX002DsuchZX0029'
    assert lang_any['id_1'] == '_Reserved'
    assert lang_any['id_2'] == '__also_reserved'
    assert lang_any['id_3'] == 'register'
    assert lang_any['id_4'] == 'False_'
    assert lang_any['id_5'] == 'return_'
    assert lang_any['id_6'] == 'return:poop:'
    assert lang_any['id_7'] == 'I_ZX2764_UAVCAN'
    assert lang_any['id_8'] == 'I_0x2764_UAVCAN'
    assert lang_any['id_9'] == 'str_'
    assert lang_any['id_A'] == 'strr'
    assert lang_any['id_B'] == 'UINT_FOO_MIN'
    assert lang_any['id_C'] == 'INT_C'
    assert lang_any['id_D'] == 'LC_Is_reserved'
    assert lang_any['id_E'] == 'NOT_ATOMIC_YO'
    assert lang_any['id_F'] == 'ATOMIC_YO'

    assert '_Flight__time' == py_filter_id(Dummy('_Flight__time'))


def test_lang_py_explicit(gen_paths, unique_name_evaluator):  # type: ignore
    """
    Generates and verifies JSON with values filtered using the python language support module using
    explicit language feature names.
    """

    ptest_lang_py(gen_paths, False, unique_name_evaluator)


def test_language_object() -> None:
    """
    Verify that the Language module object works as required.
    """
    language = Language('c', '.h')

    assert 'c' == language.name
    assert language.get_module() is not None

    found_id = False
    for function_tuple in inspect.getmembers(language.get_module(), inspect.isfunction):
        if 'filter_id' == function_tuple[0]:
            found_id = True
            break
    assert found_id


def test_language_context() -> None:
    """
    Verify that the LanguageContext objects works as required.
    """
    context_w_no_target = LanguageContext(extension='.json')

    assert None is context_w_no_target.get_target_language()
    assert 'c' in context_w_no_target.get_supported_languages()
    assert 'cpp' in context_w_no_target.get_supported_languages()
    assert 'py' in context_w_no_target.get_supported_languages()

    assert context_w_no_target.get_id_filter() is not None
    assert 'if' == context_w_no_target.get_id_filter()('if')

    context_w_target = LanguageContext('c')

    assert context_w_target.get_target_language() is not None
    assert context_w_target.get_id_filter() is not None
    assert '_if' == context_w_target.get_id_filter()('if')


def test_either_target_or_extension() -> None:
    """
    LanguageContext requires either a target or an extension or both but not
    neither.
    """
    _ = LanguageContext(target_language='py')
    _ = LanguageContext(extension='.py')
    _ = LanguageContext(target_language='py', extension='.py')
    with pytest.raises(ValueError):
        _ = LanguageContext()

    with pytest.raises(KeyError):
        _ = LanguageContext('foobar')
