"""Sphinx configuration file for the openEuler Intelligence Framework."""

import sys
from pathlib import Path

project = "openEuler Intelligence Framework"
copyright = "2025, Huawei Technologies Co., Ltd."  # noqa: A001
author = "sig-intelligence"
release = "0.10.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib.autodoc_pydantic",
    "sphinxcontrib.plantuml",
]

templates_path = ["_templates"]
exclude_patterns = []

language = "zh_CN"
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

autodoc_pydantic_model_show_config_summary = True
autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_show_field_summary = True
autodoc_pydantic_field_show_default = True

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

plantuml_output_format = "svg"
plantuml = (
    r"java -jar C:\Users\ObjectNF\scoop\apps\plantuml\current\plantuml.jar"
)
