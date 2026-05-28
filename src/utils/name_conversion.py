"""
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""


def lower_to_camel(name: str) -> str:
    """
    Converts lower-case names in the format of lower_case_name to CamelCase.

    name_in_lower_case -> NameInCamelCase.

    Args:
        name (str): Lower-case name to convert.

    Returns:
        (str): Camel case version of the name

    Raises:
        ValueError if the input name is not a single word.
    """
    if " " in name:
        raise ValueError("Input name must be a single word.")

    parts = name.split("_")
    return "".join(part.capitalize() for part in parts)


def camel_to_lower(name: str) -> str:
    """
    Converts CamelCase names to lower-case names in the format of lower_case_with_underscores.

    NameInCamelCase -> name_in_camel_case.

    Args:
        name (str): CamelCase name to convert.

    Returns:
        (str): Lower-case version of the name.

    Raises:
        ValueError if the input name is not a single word.
    """
    if " " in name:
        raise ValueError("Input name must be a single word.")

    res = [name[0].lower()]
    for c in name[1:]:
        if c.isupper():
            res.append("_")
            res.append(c.lower())
        else:
            res.append(c)
    return "".join(res)
