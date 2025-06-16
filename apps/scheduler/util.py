# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""YAML表示器"""

def yaml_str_presenter(dumper, data):  # noqa: ANN001, ANN201, D103
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

def yaml_enum_presenter(dumper, data):  # noqa: ANN001, ANN201, D103
    return dumper.represent_scalar("tag:yaml.org,2002:str", data.value)
