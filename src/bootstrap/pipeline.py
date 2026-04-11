"""
Bootstrap pipeline — defines the order of onboarding steps.

To add a new step:
  1. Create a new file in bootstrap/steps/ with a step() function returning a step dict
  2. Import it here and add it to build_pipeline()

To reorder: change the list order below.
To remove: delete or comment out the entry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bootstrap.steps import ai_provider, done, profile, welcome

if TYPE_CHECKING:
    from collections.abc import Callable


def build_pipeline(on_config_ready: Callable) -> list[dict]:
    """Build the ordered list of bootstrap steps."""
    return [
        welcome.step(),
        profile.step(),
        ai_provider.step(on_config_ready),
        # Future steps go here, e.g.:
        # campus_selection.step(),
        done.step(),
    ]
