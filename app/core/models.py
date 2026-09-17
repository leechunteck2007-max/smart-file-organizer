from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class FileRecord:
    id: str
    filename: str
    extension: str
    size: int
    created_at: float
    modified_at: float
    original_path: str
    current_path: str
    hash: str = ''
    protected: bool = False
    project_member: bool = False

@dataclass
class ClassificationResult:
    category: str
    subcategory: str
    confidence: int
    reason: str
    classifier: str = 'RuleBasedClassifier'
    suggested_destination: str = ''

@dataclass
class MovePlan:
    file: FileRecord
    classification: ClassificationResult
    destination: str
    status: str = 'Awaiting approval'

@dataclass
class FileAction:
    action_id: str
    timestamp: str
    action_type: str
    source: str
    destination: str
    hash_before: str
    success: bool
    error: str
    undo_available: bool

@dataclass
class UserProfile:
    name: str = 'Mixed'
    school: str = ''
    programme: str = ''
    year: str = ''
    courses: list[str] = field(default_factory=list)

@dataclass
class Rule:
    pattern: str
    category: str
    confidence: int = 95

@dataclass
class ProtectedPath:
    path: str
    category: str

@dataclass
class DuplicateGroup:
    hash: str
    files: list[str]
    savings: int

@dataclass
class AgentStatus:
    paused: bool = False
    last_scan: str = ''

class ClassifierProvider(Protocol):
    def classify(self, record: FileRecord) -> ClassificationResult: ...
