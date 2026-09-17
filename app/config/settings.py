import json
from pathlib import Path

PROFILES = ['Student', 'Teacher', 'Office', 'Developer', 'Personal', 'Mixed']

def defaults():
    return dict(profile='Mixed', folders=[], library=str(Path.home() / 'File Library'),
                auto=False, threshold=95, review_threshold=80, paused=False,
                ignored=[], protected=[], rules=[], onboarded=False,
                startup_paused=False, duplicates=True, student={}, controlled_verified=False, controlled_actions=[])

def validate(value):
    data = defaults()
    data.update({k: v for k, v in value.items() if k in data})
    if data['profile'] not in PROFILES: raise ValueError('Unknown profile')
    for key in ('threshold', 'review_threshold'):
        minimum = 95 if key == 'threshold' else 80
        if type(data[key]) is not int or not minimum <= data[key] <= 100:
            raise ValueError(f'{key} must be {minimum}–100')
    for key in ('auto', 'paused', 'onboarded', 'startup_paused', 'duplicates', 'controlled_verified'):
        if type(data[key]) is not bool: raise ValueError('Invalid boolean setting')
    for key in ('folders', 'ignored', 'protected'):
        if not isinstance(data[key], list) or any(not isinstance(p, str) or not Path(p).is_absolute() for p in data[key]):
            raise ValueError('Folder paths must be absolute')
    if any(Path(p).parent == Path(p) for p in data['folders']): raise ValueError('Whole-drive monitoring disabled')
    if not isinstance(data['library'], str) or not Path(data['library']).is_absolute():
        raise ValueError('Library must be absolute')
    if not isinstance(data['rules'], list): raise ValueError('Invalid rules')
    for rule in data['rules']:
        if set(rule) != {'pattern', 'category', 'confidence'} or not isinstance(rule['pattern'], str):
            raise ValueError('Invalid rule')
        parts = Path(rule['category']).parts
        if not parts or Path(rule['category']).is_absolute() or any(p in ('..', '.') for p in parts) or ':' in rule['category']:
            raise ValueError('Category must be a relative folder')
        if type(rule['confidence']) is not int or not 0 <= rule['confidence'] <= 100: raise ValueError('Invalid confidence')
    return data
