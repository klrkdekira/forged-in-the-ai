"""Export the WebSocket state payload schema for client contract review."""

import json

from ai.tools import GameState


def main() -> None:
    """Write the canonical GameState JSON Schema to stdout."""
    print(json.dumps(GameState.model_json_schema(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
