from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal

class Requirement(BaseModel):
    id: str
    type: Literal['business','functional','non-functional','integration','data','security','operational'] = 'functional'
    title: str
    description: str
    priority: Literal['high','medium','low'] = 'medium'
    source_refs: list[str] = Field(default_factory=list)
    status: Literal['new','existing','changed','resolved'] = 'new'

class Gap(BaseModel):
    id: str
    category: str
    description: str
    severity: Literal['high','medium','low'] = 'medium'
    business_impact: str = ''
    question: str
    question_type: Literal['business','technical'] = 'business'
    related_requirement_ids: list[str] = Field(default_factory=list)

class AnalysisResult(BaseModel):
    requirements: list[Requirement] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
