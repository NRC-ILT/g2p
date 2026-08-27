# Information for maintainers

## Publishing g2p

Publication of g2p to PyPI is automated via the [pythonpublish.md](./.github/workflows/pythonpublish.yml) workflow.

To prepare and trigger package publication:

- Make sure [.SETUPTOOLS_SCM_PRETEND_VERSION](./.SETUPTOOLS_SCM_PRETEND_VERSION) matches the major.minor of the version to publish.
- Commit the changes if any.
- Create an annotated tag with the version number, e.g.: `git tag -a v2.0.1 -m v2.0.1`.
- Push the tag, which will trigger the pythonpublish release workflow and hatch build will build and publish using the tag version, e.g., `git push origin v2.0.1`.
- Note: only builds from tagged commits will have proper release versions, others will have dev versions

## Versioning system

We use dynamic versioning based on the latest version tag.

In CI tests, tags are not fetched so the version is faked using [.SETUPTOOLS_SCM_PRETEND_VERSION](./.SETUPTOOLS_SCM_PRETEND_VERSION).

To start development on a new version without publishing it, create a dev tag, e.g.

    git tag -a v2.3.4.dev -m 'Starting development on v2.3.4'
