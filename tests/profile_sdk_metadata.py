"""Explicit historical source provider for counterfeit SDK/gate unit controls."""

DERIVED_MANIFEST = 'third-party/sdk/geckoview-157.0.1-editable-selection.json'


def historical_source(reader, source, path):
    # Historical official fixtures predate the derived SDK. Reading the current
    # worktree manifest would relabel those adversarial inputs as a new runtime.
    if path == DERIVED_MANIFEST:
        raise FileNotFoundError('Historical counterfeit source has no derived SDK manifest')
    return reader(source, path)


def historical_git_output(reader, expected_source, tree):
    def output(command, **kwargs):
        if command == ['git', 'rev-parse', expected_source + '^{tree}']:
            return tree
        if len(command) == 3 and command[:2] == ['git', 'show']:
            source, separator, path = command[2].partition(':')
            if separator and source == expected_source:
                return historical_source(reader, source, path)
        raise AssertionError('Unexpected Git request in historical counterfeit source: ' + repr(command))
    return output
