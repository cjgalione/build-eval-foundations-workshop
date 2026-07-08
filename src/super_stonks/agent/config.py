import os

import braintrust

DEFAULT_BRAINTRUST_PROJECT_NAME = "advanced-evals-workshop"

def get_braintrust_project_name() -> str:
    # BRAINTRUST_DEFAULT_PROJECT is the workshop standard (the var the bt CLI reads),
    # so agent traffic from the CLI and Streamlit lands in the same project the CLI uses.
    # BRAINTRUST_PROJECT_NAME is kept as a fallback for older setups.
    project_name = (
        os.getenv("BRAINTRUST_DEFAULT_PROJECT", "").strip()
        or os.getenv("BRAINTRUST_PROJECT_NAME", "").strip()
    )
    return project_name or DEFAULT_BRAINTRUST_PROJECT_NAME


def init_braintrust_logger():
    return braintrust.init_logger(project=get_braintrust_project_name())
