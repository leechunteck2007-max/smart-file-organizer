from pathlib import Path

class UndoEngine:
    def __init__(self, mover): self.mover = mover
    def undo(self, action):
        if action['status'] != 'SUCCESS' or not action['undo_available']: raise ValueError('Undo unavailable')
        if not Path(action['source']).parent.is_dir(): raise ValueError('Original folder missing; review required')
        return self.mover.execute(action['destination'], action['source'], 'Restore approved move', 100, undo_of=action)
