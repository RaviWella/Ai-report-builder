"""Business domains for schema linking (aligned with question bank ``eval_domain``)."""
from __future__ import annotations

from enum import Enum


class DatamartDomain(str, Enum):
    PAYROLL = "payroll"
    LEAVE = "leave"
    ATTENDANCE = "attendance"
    WORKFORCE = "workforce"
    RECRUITMENT = "recruitment"
    ATTRITION = "attrition"
    HEADCOUNT = "headcount"
    MIXED = "mixed"
    UNKNOWN = "unknown"
