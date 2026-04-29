from enum import Enum


class PageType(str, Enum):
    ARTICLE = "Article"
    ANOMALY = "Anomaly"
    ARTIFACT = "Artifact"
    LOCATION = "Location"
    INCIDENT = "Incident"
    EXPEDITION = "Expedition"
    RESEARCHER_NOTE = "Researcher Note"


class PageStatus(str, Enum):
    DRAFT = "Draft"
    REVIEW = "Review"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"
    REDACTED = "Redacted"


class Visibility(str, Enum):
    PUBLIC = "Public"
    INTERNAL = "Internal"
