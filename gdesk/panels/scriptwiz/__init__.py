from ... import config
from .proxy import ScriptWizardProxy

if config['qapp']:
    from .panel import ScriptWizardPanel