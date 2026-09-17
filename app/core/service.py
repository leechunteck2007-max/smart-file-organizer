from pathlib import Path
from datetime import datetime
import platform
from app.config.settings import validate
from app.database.store import Store
from app.safety.policy import SafetyPolicy
from app.scanner.scanner import scan
from app.classifier.rule_based import RuleBasedClassifier
from app.core.models import MovePlan
from app.actions.move import MoveEngine
from app.undo.engine import UndoEngine
from app import __version__

class Service:
    def __init__(self, state):
        self.state = Path(state)
        self.store = Store(self.state/'librarian.sqlite')
        self.settings = validate(self.store.load())
        if self.settings['startup_paused']: self.settings['paused'] = True
        self.plans = []; self.errors = []; self.last_scan = ''; self.groups = []
        self.configure(); self.mover.recover()
    def configure(self):
        self.policy = SafetyPolicy(self.settings, self.state)
        self.classifier = RuleBasedClassifier(self.settings, self.policy)
        self.mover = MoveEngine(self.store, self.policy); self.undo = UndoEngine(self.mover)
    def save(self):
        self.settings = validate(self.settings); self.store.save(self.settings); self.configure()
    def scan(self):
        records, self.errors = scan(self.settings['folders'], self.policy)
        ignored = self.store.ignored()
        self.plans = [MovePlan(r, self.classifier.classify(r), '') for r in records if r.current_path not in ignored]
        for plan in self.plans: plan.destination = plan.classification.suggested_destination
        self.last_scan = datetime.now().isoformat(timespec='seconds')
        return self.plans
    def diagnostic(self):
        from collections import Counter
        return dict(version=__version__, os=platform.platform(), files=len(self.plans),
            categories=dict(Counter(p.classification.category if p.classification.category in {'Education','Teaching','Work','Documents','Finance','Media','Photos','Screenshots','Videos','Projects','Installers','Archives','Personal','Inbox','Unclassified','Protected'} else 'Custom' for p in self.plans)),
            error_codes=dict(Counter(self.errors)), duplicate_groups=len(self.groups),
            auto_enabled=self.settings['auto'], paused=self.settings['paused'])

    def record_controlled(self, action_ids):
        self.settings['controlled_actions'] = action_ids
        self.save()
    def verify_controlled_undo(self):
        from app.scanner.scanner import sha256
        ids = self.settings['controlled_actions']
        if not 5 <= len(ids) <= 20: return False
        actions = {a['id']: a for a in self.store.history()}
        for action_id in ids:
            a = actions.get(action_id)
            if not a or a['status'] != 'SUCCESS' or a['undo_available']: return False
            source = Path(a['source'])
            if not source.is_file() or sha256(source) != a['hash']: return False
        self.settings['controlled_verified'] = True
        self.save()
        return True
