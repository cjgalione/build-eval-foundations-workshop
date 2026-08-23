import os

import braintrust

def get_braintrust_project_name() -> str:
    """Return the attendee's isolated workshop project, or fail before logging."""
    project_name = os.getenv("BRAINTRUST_DEFAULT_PROJECT", "").strip()
    if not project_name:
        raise RuntimeError(
            "Set BRAINTRUST_DEFAULT_PROJECT to your individual workshop project, "
            "for example <your-name>-eval-foundations."
        )
    return project_name


def init_braintrust_logger():
    return braintrust.init_logger(project=get_braintrust_project_name())
