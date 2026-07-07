import os

import braintrust

DEFAULT_BRAINTRUST_PROJECT_NAME = "advanced-evals-workshop"

def get_braintrust_project_name() -> str:
    project_name = os.getenv("BRAINTRUST_PROJECT_NAME", "").strip()
    return project_name or DEFAULT_BRAINTRUST_PROJECT_NAME


def init_braintrust_logger():
    return braintrust.init_logger(project=get_braintrust_project_name())
