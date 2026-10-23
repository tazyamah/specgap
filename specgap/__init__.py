"""specgap: 仕様の漏れ検査器・レビュー画面・実装の保証（試作）。"""

from .checks import ERROR, INFO, WARNING, Finding, Report, check
from .model import SpecError, load, parse

__all__ = ["check", "load", "parse", "Report", "Finding", "SpecError", "ERROR", "WARNING", "INFO"]
